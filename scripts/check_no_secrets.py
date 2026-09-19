#!/usr/bin/env python3
"""Scan publishable repository files without printing matched secret values."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import Iterable


RULES = (
    ("tavily-api-key", re.compile(r"\btvly-[A-Za-z0-9_-]{16,}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("openai-api-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    (
        "private-key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "personal-windows-user-path",
        re.compile(r"\b[A-Za-z]:[\\/]+Users[\\/]+[^<>%\\/\s\"'`,;:{}]+", re.IGNORECASE),
    ),
)

SKIPPED_PARTS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv"}


def publishable_files(root: Path) -> list[Path]:
    """Return tracked and non-ignored files, with a filesystem fallback outside Git."""
    if (root / ".git").exists():
        completed = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=root,
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0:
            return sorted(
                root / Path(item.decode("utf-8", errors="surrogateescape"))
                for item in completed.stdout.split(b"\0")
                if item
            )

    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and not any(part in SKIPPED_PARTS for part in path.parts)
    )


def scan(paths: Iterable[Path], root: Path) -> list[tuple[str, int, str]]:
    findings: list[tuple[str, int, str]] = []
    for path in paths:
        try:
            raw = path.read_bytes()
        except OSError:
            findings.append((path.relative_to(root).as_posix(), 0, "unreadable-file"))
            continue
        if b"\0" in raw:
            continue
        text = raw.decode("utf-8", errors="ignore")
        relative = path.relative_to(root).as_posix()
        for line_number, line in enumerate(text.splitlines(), start=1):
            for rule_name, pattern in RULES:
                if pattern.search(line):
                    findings.append((relative, line_number, rule_name))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan files that could be published without echoing matched values."
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()

    if not root.is_dir():
        parser.error(f"not a directory: {root}")

    findings = scan(publishable_files(root), root)
    if findings:
        print("Potential secrets or personal paths found:")
        for relative, line_number, rule_name in findings:
            location = f"{relative}:{line_number}" if line_number else relative
            print(f"- {location} [{rule_name}]")
        return 1

    print("No high-confidence secrets or personal profile paths found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
