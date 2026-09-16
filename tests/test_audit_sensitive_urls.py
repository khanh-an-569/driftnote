from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "web-to-obsidian"
    / "scripts"
    / "audit_sensitive_urls.py"
)


def load_audit_module():
    if not SCRIPT_PATH.is_file():
        raise AssertionError("audit_sensitive_urls.py is not implemented")
    spec = importlib.util.spec_from_file_location("audit_sensitive_urls", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def source_note(
    source_url: str,
    source_id: str = "old-source-id",
    *,
    canonical_url: str | None = None,
    callout_url: str | None = None,
) -> str:
    canonical_url = canonical_url if canonical_url is not None else source_url
    callout_url = callout_url if callout_url is not None else source_url
    return (
        "---\n"
        "type: source\n"
        f'source_id: "{source_id}"\n'
        'title: "Example"\n'
        f'source_url: "{source_url}"\n'
        f'canonical_url: "{canonical_url}"\n'
        "---\n\n"
        "# Example\n\n"
        f"> [Mở liên kết gốc]({callout_url})\n\n"
        "## Ghi chú của tôi\n"
    )


class AuditSensitiveUrlsTests(unittest.TestCase):
    def test_dry_run_reports_risk_without_mutating_or_exposing_values(self) -> None:
        audit = load_audit_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_secret = "test-only-secret"
            note_path = Path(temp_dir) / "capture.md"
            original = source_note(f"https://example.com/item?token={fake_secret}&ok=1")
            note_path.write_text(original, encoding="utf-8")

            result = audit.audit_vault(Path(temp_dir), apply=False)
            output = json.dumps(result, ensure_ascii=False)

            self.assertEqual(note_path.read_text(encoding="utf-8"), original)
            self.assertEqual(result["changed_files"], 0)
            self.assertEqual(result["finding_count"], 1)
            self.assertNotIn(fake_secret, output)
            self.assertEqual(result["findings"][0]["path"], str(note_path.resolve()))
            self.assertEqual(
                result["findings"][0]["issues"],
                [
                    {"field": "source_url", "reason_code": "sensitive_query"},
                    {"field": "canonical_url", "reason_code": "sensitive_query"},
                    {"field": "source_callout", "reason_code": "sensitive_query"},
                ],
            )
            self.assertFalse(result["findings"][0]["manual_review"])
            self.assertNotIn("fields", result["findings"][0])
            self.assertNotIn("reason_codes", result["findings"][0])

    def test_apply_redacts_structured_urls_and_recomputes_source_id(self) -> None:
        audit = load_audit_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_secret = "test-only-secret"
            note_path = Path(temp_dir) / "capture.md"
            note_path.write_text(
                source_note(f"https://example.com/item?token={fake_secret}&ok=1"),
                encoding="utf-8",
            )

            result = audit.audit_vault(Path(temp_dir), apply=True)
            updated = note_path.read_text(encoding="utf-8")

            self.assertEqual(result["changed_files"], 1)
            self.assertNotIn(fake_secret, updated)
            self.assertIn('source_url: "https://example.com/item?ok=1"', updated)
            self.assertIn('canonical_url: "https://example.com/item?ok=1"', updated)
            self.assertIn("source_url_redacted: true", updated)
            self.assertIn("canonicalization_version: 2", updated)
            self.assertIn('source_id: "e9bde445a67bc7c1"', updated)
            self.assertIn("> [Mở liên kết gốc](https://example.com/item?ok=1)", updated)

    def test_audits_sensitive_canonical_url_independently(self) -> None:
        audit = load_audit_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            marker = "canonical-only-secret"
            note_path = Path(temp_dir) / "canonical.md"
            note_path.write_text(
                source_note(
                    "https://example.com/item?ok=1",
                    canonical_url=f"https://example.com/item?token={marker}&ok=1",
                    callout_url="https://example.com/item?ok=1",
                ),
                encoding="utf-8",
            )

            result = audit.audit_vault(Path(temp_dir), apply=True)
            updated = note_path.read_text(encoding="utf-8")

            self.assertEqual(result["changed_files"], 1)
            self.assertNotIn(marker, json.dumps(result))
            self.assertNotIn(marker, updated)
            self.assertIn(
                {"field": "canonical_url", "reason_code": "sensitive_query"},
                result["findings"][0]["issues"],
            )

    def test_audits_sensitive_source_callout_independently(self) -> None:
        audit = load_audit_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            marker = "callout-only-secret"
            note_path = Path(temp_dir) / "callout.md"
            note_path.write_text(
                source_note(
                    "https://example.com/item?ok=1",
                    canonical_url="https://example.com/item?ok=1",
                    callout_url=f"https://example.com/item?token={marker}&ok=1",
                ),
                encoding="utf-8",
            )

            result = audit.audit_vault(Path(temp_dir), apply=True)
            updated = note_path.read_text(encoding="utf-8")

            self.assertEqual(result["changed_files"], 1)
            self.assertNotIn(marker, json.dumps(result))
            self.assertNotIn(marker, updated)
            self.assertIn(
                {"field": "source_callout", "reason_code": "sensitive_query"},
                result["findings"][0]["issues"],
            )

    def test_invalid_structured_url_requires_manual_review(self) -> None:
        audit = load_audit_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            note_path = Path(temp_dir) / "invalid.md"
            original = source_note(
                "https://example.com/item",
                canonical_url="not a valid url",
                callout_url="https://example.com/item",
            )
            note_path.write_text(original, encoding="utf-8")

            result = audit.audit_vault(Path(temp_dir), apply=True)

            self.assertEqual(result["finding_count"], 1)
            self.assertEqual(result["changed_files"], 0)
            self.assertEqual(result["manual_review_count"], 1)
            self.assertEqual(note_path.read_text(encoding="utf-8"), original)
            self.assertIn(
                {"field": "canonical_url", "reason_code": "invalid_url"},
                result["findings"][0]["issues"],
            )

    def test_identity_mismatch_requires_manual_review(self) -> None:
        audit = load_audit_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            note_path = Path(temp_dir) / "mismatch.md"
            original = source_note(
                "https://example.com/one",
                canonical_url="https://example.com/two",
                callout_url="https://example.com/one",
            )
            note_path.write_text(original, encoding="utf-8")

            result = audit.audit_vault(Path(temp_dir), apply=True)

            self.assertEqual(result["changed_files"], 0)
            self.assertEqual(result["manual_review_count"], 1)
            self.assertEqual(note_path.read_text(encoding="utf-8"), original)
            self.assertIn(
                {"field": "canonical_url", "reason_code": "identity_mismatch"},
                result["findings"][0]["issues"],
            )

    def test_apply_stops_when_redaction_would_create_duplicate_identity(self) -> None:
        audit = load_audit_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first.md"
            second = Path(temp_dir) / "second.md"
            first_original = source_note("https://example.com/item?token=one", "first")
            second_original = source_note("https://example.com/item?token=two", "second")
            first.write_text(first_original, encoding="utf-8")
            second.write_text(second_original, encoding="utf-8")

            result = audit.audit_vault(Path(temp_dir), apply=True)

            self.assertEqual(result["changed_files"], 0)
            self.assertEqual(result["manual_review_count"], 2)
            self.assertEqual(first.read_text(encoding="utf-8"), first_original)
            self.assertEqual(second.read_text(encoding="utf-8"), second_original)
            self.assertNotIn("token=one", json.dumps(result))
            self.assertNotIn("token=two", json.dumps(result))
            for finding in result["findings"]:
                self.assertIn(
                    {"field": "canonical_url", "reason_code": "duplicate_identity"},
                    finding["issues"],
                )

    def test_concurrent_edit_is_preserved_and_reported_for_manual_review(self) -> None:
        audit = load_audit_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            note_path = Path(temp_dir) / "capture.md"
            note_path.write_text(
                source_note("https://example.com/item?token=secret"),
                encoding="utf-8",
            )
            concurrently_edited = source_note("https://example.com/concurrent")
            original_write_atomic = audit._write_atomic

            def race(path: Path, text: str, expected_text: str) -> bool:
                path.write_text(concurrently_edited, encoding="utf-8")
                return original_write_atomic(path, text, expected_text)

            with mock.patch.object(audit, "_write_atomic", side_effect=race):
                result = audit.audit_vault(Path(temp_dir), apply=True)

            self.assertEqual(result["changed_files"], 0)
            self.assertEqual(result["manual_review_count"], 1)
            self.assertEqual(note_path.read_text(encoding="utf-8"), concurrently_edited)
            self.assertIn(
                {"field": "note", "reason_code": "concurrent_modification"},
                result["findings"][0]["issues"],
            )


if __name__ == "__main__":
    unittest.main()
