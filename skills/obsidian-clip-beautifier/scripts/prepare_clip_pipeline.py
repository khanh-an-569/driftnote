#!/usr/bin/env python3
"""Preview or install non-destructive Obsidian web-clip pipeline assets."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = SKILL_ROOT / "assets"

DIRECTORIES = (
    Path("00 Inbox/Web"),
    Path("00 System/Web Clipper"),
    Path(".obsidian/snippets"),
)

FILES = (
    (
        ASSET_ROOT / "web-clip-clean-reading-clipper.json",
        Path("00 System/Web Clipper/web-clip-clean-reading-clipper.json"),
    ),
    (
        ASSET_ROOT / "obsidian-clip-beautifier.css",
        Path(".obsidian/snippets/obsidian-clip-beautifier.css"),
    ),
)


def resolve_vault(value: str | None) -> Path:
    candidate = value or os.environ.get("OBSIDIAN_VAULT_PATH")
    if not candidate:
        raise ValueError("Provide --vault or set OBSIDIAN_VAULT_PATH.")

    vault = Path(candidate).expanduser().resolve()
    if not vault.is_dir():
        raise ValueError(f"Vault directory does not exist: {vault}")
    if not (vault / ".obsidian").is_dir():
        raise ValueError(f"Not an initialized Obsidian vault (missing .obsidian): {vault}")
    return vault


def _file_status(source: Path, target: Path) -> str:
    if not target.exists():
        return "missing"
    if not target.is_file():
        return "conflict"
    return "unchanged" if source.read_bytes() == target.read_bytes() else "conflict"


def prepare(vault: Path, *, apply: bool) -> dict[str, Any]:
    vault = vault.resolve()
    if not (vault / ".obsidian").is_dir():
        raise ValueError(f"Not an initialized Obsidian vault (missing .obsidian): {vault}")

    result: dict[str, Any] = {
        "mode": "apply" if apply else "preview",
        "vault": str(vault),
        "directories": [],
        "files": [],
    }

    for relative in DIRECTORIES:
        target = (vault / relative).resolve()
        target.relative_to(vault)
        existed = target.is_dir()
        if apply:
            target.mkdir(parents=True, exist_ok=True)
        result["directories"].append(
            {
                "path": str(target),
                "status": "unchanged" if existed else ("created" if apply else "planned"),
            }
        )

    for source, relative in FILES:
        target = (vault / relative).resolve()
        target.relative_to(vault)
        status = _file_status(source, target)
        if status == "missing" and apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                with target.open("xb") as destination:
                    destination.write(source.read_bytes())
                status = "created"
            except FileExistsError:
                status = _file_status(source, target)
        elif status == "missing":
            status = "planned"

        result["files"].append(
            {
                "path": str(target),
                "source": str(source),
                "status": status,
            }
        )

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview or install the Obsidian web-clip beautification assets."
    )
    parser.add_argument(
        "--vault",
        help="Obsidian vault root. Defaults to OBSIDIAN_VAULT_PATH.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create missing directories and files. Existing differing files are never overwritten.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        vault = resolve_vault(args.vault)
        result = prepare(vault, apply=args.apply)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    has_conflict = any(item["status"] == "conflict" for item in result["files"])
    return 1 if has_conflict else 0


if __name__ == "__main__":
    sys.exit(main())
