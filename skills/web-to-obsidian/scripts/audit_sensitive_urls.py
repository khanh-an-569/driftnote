#!/usr/bin/env python3
"""Audit and optionally redact sensitive URLs in existing Obsidian source notes."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import save_capture  # noqa: E402


FRONTMATTER_PATTERN = re.compile(r"\A---\r?\n(?P<body>.*?)\r?\n---(?:\r?\n|\Z)", re.DOTALL)
SOURCE_LINK_PATTERN = re.compile(
    r"(?m)^>\s*\[(?P<label>Mở liên kết gốc|Open original(?: link)?|"
    r"Open original link / Mở liên kết gốc)\]\((?P<url>.*)\)\s*$"
)


@dataclass
class UrlObservation:
    field: str
    value: str
    safe_url: save_capture.SafeUrl | None


@dataclass
class NoteAudit:
    path: Path
    text: str
    frontmatter: str
    observations: list[UrlObservation]
    target_safe_url: save_capture.SafeUrl | None
    issues: list[dict[str, str]]
    manual_review: bool = False

    @property
    def is_finding(self) -> bool:
        return bool(self.issues)


def _load_note(path: Path) -> NoteAudit | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    match = FRONTMATTER_PATTERN.match(text)
    if not match:
        return None
    frontmatter = match.group("body")
    fields = save_capture._frontmatter_fields(text)
    if fields.get("type") != "source":
        return None

    raw_observations: list[tuple[str, str]] = []
    for field in ("source_url", "canonical_url"):
        if fields.get(field):
            raw_observations.append((field, fields[field]))
    raw_observations.extend(
        ("source_callout", link_match.group("url"))
        for link_match in SOURCE_LINK_PATTERN.finditer(text)
    )
    if not raw_observations:
        return None

    observations: list[UrlObservation] = []
    issues: list[dict[str, str]] = []
    manual_review = False
    for field, value in raw_observations:
        try:
            safe_url = save_capture.sanitize_url(value)
        except save_capture.CaptureError:
            safe_url = None
            manual_review = True
            _add_issue(issues, field, "invalid_url")
        else:
            for reason_code in safe_url.reason_codes:
                _add_issue(issues, field, reason_code)
        observations.append(UrlObservation(field, value, safe_url))

    source_observation = next(
        (observation for observation in observations if observation.field == "source_url"),
        None,
    )
    target_safe_url = source_observation.safe_url if source_observation else None
    if target_safe_url is None:
        manual_review = True

    valid_observations = [
        observation for observation in observations if observation.safe_url is not None
    ]
    if valid_observations:
        reference = target_safe_url or valid_observations[0].safe_url
        assert reference is not None
        mismatches = [
            observation
            for observation in valid_observations
            if observation.safe_url is not None
            and observation.safe_url.canonical_url != reference.canonical_url
        ]
        if mismatches:
            manual_review = True
            for observation in mismatches:
                _add_issue(issues, observation.field, "identity_mismatch")

    return NoteAudit(
        path=path,
        text=text,
        frontmatter=frontmatter,
        observations=observations,
        target_safe_url=target_safe_url,
        issues=issues,
        manual_review=manual_review,
    )


def _add_issue(issues: list[dict[str, str]], field: str, reason_code: str) -> None:
    issue = {"field": field, "reason_code": reason_code}
    if issue not in issues:
        issues.append(issue)


def _replace_frontmatter_field(frontmatter: str, name: str, value: str) -> str:
    replacement = f"{name}: {value}"
    pattern = re.compile(rf"(?m)^{re.escape(name)}:\s*.*$")
    if pattern.search(frontmatter):
        return pattern.sub(lambda _: replacement, frontmatter, count=1)
    if name == "source_url_redacted":
        canonical = re.compile(r"(?m)^canonical_url:\s*.*$")
        if canonical.search(frontmatter):
            return canonical.sub(
                lambda match: f"{match.group(0)}\n{replacement}", frontmatter, count=1
            )
    if name == "canonicalization_version":
        canonical = re.compile(r"(?m)^canonical_url:\s*.*$")
        if canonical.search(frontmatter):
            return canonical.sub(
                lambda match: f"{match.group(0)}\n{replacement}", frontmatter, count=1
            )
    return f"{frontmatter.rstrip()}\n{replacement}"


def _updated_text(note: NoteAudit) -> str:
    safe = note.target_safe_url
    assert safe is not None
    frontmatter = note.frontmatter
    frontmatter = _replace_frontmatter_field(
        frontmatter, "source_url", json.dumps(safe.source_url, ensure_ascii=False)
    )
    frontmatter = _replace_frontmatter_field(
        frontmatter, "canonical_url", json.dumps(safe.canonical_url, ensure_ascii=False)
    )
    frontmatter = _replace_frontmatter_field(
        frontmatter,
        "source_id",
        json.dumps(save_capture.source_id_for(safe.canonical_url)),
    )
    frontmatter = _replace_frontmatter_field(
        frontmatter, "source_url_redacted", "true"
    )
    frontmatter = _replace_frontmatter_field(
        frontmatter, "canonicalization_version", "2"
    )

    match = FRONTMATTER_PATTERN.match(note.text)
    assert match is not None
    updated = note.text[: match.start("body")] + frontmatter + note.text[match.end("body") :]

    def replace_source_link(link_match: re.Match[str]) -> str:
        return f"> [{link_match.group('label')}]({safe.source_url})"

    return SOURCE_LINK_PATTERN.sub(replace_source_link, updated)


def _write_atomic(path: Path, text: str, expected_text: str) -> bool:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        try:
            current_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return False
        if current_text != expected_text:
            return False
        os.replace(temp_path, path)
        temp_path = None
        return True
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def audit_vault(vault: Path, *, apply: bool = False) -> dict[str, object]:
    root = vault.expanduser().resolve()
    if not root.is_dir():
        raise save_capture.CaptureError("Vault does not exist or is not a directory.")

    notes = [
        note
        for path in save_capture._iter_markdown_files(root)
        if (note := _load_note(path)) is not None
    ]
    identities: dict[str, list[NoteAudit]] = {}
    for note in notes:
        if note.target_safe_url is not None:
            identities.setdefault(note.target_safe_url.canonical_url, []).append(note)
    for matching_notes in identities.values():
        if len(matching_notes) > 1:
            for note in matching_notes:
                note.manual_review = True
                _add_issue(note.issues, "canonical_url", "duplicate_identity")

    findings = [note for note in notes if note.is_finding]
    changed_files = 0
    if apply:
        for note in findings:
            if note.manual_review:
                continue
            if _write_atomic(note.path, _updated_text(note), note.text):
                changed_files += 1
            else:
                note.manual_review = True
                _add_issue(note.issues, "note", "concurrent_modification")

    return {
        "status": "applied" if apply else "dry-run",
        "files_scanned": len(notes),
        "finding_count": len(findings),
        "manual_review_count": sum(note.manual_review for note in findings),
        "changed_files": changed_files,
        "findings": [
            {
                "path": str(note.path.resolve()),
                "issues": note.issues,
                "manual_review": note.manual_review,
            }
            for note in findings
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True, help="Obsidian vault to audit")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Redact structured fields; the default is read-only dry-run",
    )
    return parser


def main() -> int:
    save_capture._configure_utf8_console()
    args = build_parser().parse_args()
    try:
        result = audit_vault(Path(args.vault), apply=args.apply)
    except (save_capture.CaptureError, OSError, UnicodeError, ValueError) as exc:
        print(
            json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
