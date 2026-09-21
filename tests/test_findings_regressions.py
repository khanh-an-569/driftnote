import tempfile
import unittest
from pathlib import Path

from markdown_it import MarkdownIt
from test_save_capture import save_capture, make_args
from test_audit_sensitive_urls import load_audit_module
import test_check_no_secrets


class FindingsRegressionTests(unittest.TestCase):
    def test_audit_apply_keeps_url_and_is_idempotent(self):
        from test_audit_sensitive_urls import source_note
        audit = load_audit_module()
        with tempfile.TemporaryDirectory() as directory:
            note = Path(directory, 'old.md')
            note.write_text(source_note('https://example.com/a)b?token=redact'), encoding='utf-8')
            first = audit.audit_vault(Path(directory), apply=True)
            self.assertEqual(first['changed_files'], 1)
            text = note.read_text(encoding='utf-8')
            self.assertIn('(<https://example.com/a)b>)', text)
            self.assertNotIn('token=', text)
            second = audit.audit_vault(Path(directory), apply=True)
            self.assertEqual(second['changed_files'], 0)
            self.assertEqual(note.read_text(encoding='utf-8'), text)

    def test_profile_roots_and_placeholders(self):
        prefix = 'C:' + '\\Users\\'
        for value, expected in [(prefix+'Alice', 1), ('"'+prefix+'Alice"', 1),
                                ('C:/'+ 'Users/alice', 1),
                                (prefix+'<username>', 0), (prefix+'%USERNAME%', 0)]:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                Path(directory, 'config.txt').write_text(value, encoding='utf-8')
                result = test_check_no_secrets.run_scan(Path(directory))
                self.assertEqual(result.returncode, expected)

    def test_invalid_url_characters_rejected(self):
        for suffix in ['a b', 'a<b', 'a>b', 'a\nb', 'a\tb', 'a\rb', 'a\x00b']:
            with self.subTest(suffix=suffix), self.assertRaises(save_capture.CaptureError):
                save_capture.sanitize_url('https://example.com/' + suffix)

    def test_leading_and_trailing_controls_are_rejected_before_whitespace_stripping(self):
        for control in ['\n', '\t', '\r', '\x00', '\x01', '\x7f']:
            for value in [control + 'https://example.com/a', 'https://example.com/a' + control]:
                with self.subTest(value=value), self.assertRaises(save_capture.CaptureError):
                    save_capture.sanitize_url(value)

        self.assertEqual(
            save_capture.sanitize_url(' https://example.com/a ').source_url,
            'https://example.com/a',
        )

    def test_raw_backslash_is_rejected_without_rewriting_percent_encoded_backslashes(self):
        for value in [
            'https://example.com/a\\.b',
            'https://example.com/a\\(b)',
            'https://example.com/a#fragment\\.part',
            'https://user\\name@example.com/a',
        ]:
            with self.subTest(value=value), self.assertRaises(save_capture.CaptureError):
                save_capture.sanitize_url(value)

        encoded = 'https://example.com/a%5C.b%5C(b)?value=%5C#fragment%5C'
        safe = save_capture.sanitize_url(encoded)
        self.assertEqual(safe.source_url, encoded)
        self.assertEqual(safe.canonical_url, encoded.split('#', maxsplit=1)[0])

    def test_audit_apply_keeps_legacy_raw_backslash_url_for_manual_review(self):
        from test_audit_sensitive_urls import source_note

        audit = load_audit_module()
        with tempfile.TemporaryDirectory() as directory:
            note = Path(directory, 'legacy.md')
            original = source_note('https://example.com/a\\.b')
            note.write_text(original, encoding='utf-8')

            result = audit.audit_vault(Path(directory), apply=True)

            self.assertEqual(result['finding_count'], 1)
            self.assertEqual(result['manual_review_count'], 1)
            self.assertEqual(result['changed_files'], 0)
            self.assertEqual(note.read_text(encoding='utf-8'), original)

    def test_capture_render_and_audit_roundtrip(self):
        audit = load_audit_module()
        for suffix in ['a)b', 'a(b', 'a(b)', 'a#x)y', 'a&copy;', 'a%29b', 'a%5C.b', 'a%5C.b%5C(b)#fragment%5C']:
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as directory:
                url = 'https://example.com/'+suffix
                result = save_capture.run_capture(make_args(directory, url=url, tavily='off'))
                note = Path(result['path'])
                text = note.read_text(encoding='utf-8')
                callout = next(line for line in text.splitlines() if line.startswith('> [Mở'))
                tokens = MarkdownIt('commonmark').parse(callout)
                hrefs = [child.attrGet('href') for token in tokens for child in (token.children or [])
                         if child.type == 'link_open']
                self.assertEqual(hrefs, [url])
                loaded = audit._load_note(note)
                self.assertFalse(loaded.manual_review)
                self.assertEqual(loaded.issues, [])
