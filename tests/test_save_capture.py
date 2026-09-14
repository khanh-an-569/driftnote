from __future__ import annotations

import argparse
import importlib.util
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "web-to-obsidian"
    / "scripts"
    / "save_capture.py"
)
SPEC = importlib.util.spec_from_file_location("save_capture", SCRIPT_PATH)
assert SPEC and SPEC.loader
save_capture = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = save_capture
SPEC.loader.exec_module(save_capture)


def make_args(vault: str, **overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "vault": vault,
        "url": "https://Example.COM/story/?utm_source=test&b=2&a=1#section",
        "title": "Một bài viết: hữu ích?",
        "author": "Tác giả",
        "published": "2026-09-13",
        "platform": "",
        "content_type": "article",
        "capture_method": "chrome",
        "content_file": None,
        "selection_file": None,
        "summary": "",
        "why": "Dùng cho dự án second brain",
        "tag": [],
        "topic": ["knowledge-management"],
        "folder": "00 Inbox/Web",
        "captured": "2026-09-13T10:00:00+07:00",
        "tavily": "off",
        "min_content_chars": 400,
        "timeout": 30.0,
        "dry_run": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class SaveCaptureTests(unittest.TestCase):
    def test_configures_utf8_console(self) -> None:
        class FakeStream:
            options: dict[str, str] | None = None

            def reconfigure(self, **kwargs: str) -> None:
                self.options = kwargs

        stdout = FakeStream()
        stderr = FakeStream()
        with mock.patch.object(save_capture.sys, "stdout", stdout), mock.patch.object(
            save_capture.sys, "stderr", stderr
        ):
            save_capture._configure_utf8_console()

        self.assertEqual(stdout.options, {"encoding": "utf-8", "errors": "replace"})
        self.assertEqual(stderr.options, {"encoding": "utf-8", "errors": "replace"})

    def test_dotenv_loads_values_without_overriding_process_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "TAVILY_API_KEY=from-file\n"
                "OBSIDIAN_VAULT_PATH=E:/skill-obsidian # local vault\n",
                encoding="utf-8",
            )
            with mock.patch.dict(
                save_capture.os.environ, {"TAVILY_API_KEY": "from-process"}, clear=True
            ):
                loaded = save_capture.load_dotenv(workspace=Path(temp_dir))
                self.assertEqual(loaded, env_path.resolve())
                self.assertEqual(save_capture.os.environ["TAVILY_API_KEY"], "from-process")
                self.assertEqual(
                    save_capture.os.environ["OBSIDIAN_VAULT_PATH"], "E:/skill-obsidian"
                )

    def test_resolves_vault_from_cli_env_then_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "web-to-obsidian.yaml").write_text(
                'vault_root: "E:/yaml-vault"\n', encoding="utf-8"
            )
            with mock.patch.dict(save_capture.os.environ, {}, clear=True):
                self.assertEqual(
                    save_capture.resolve_vault(None, workspace=workspace), "E:/yaml-vault"
                )
                save_capture.os.environ["OBSIDIAN_VAULT_PATH"] = "E:/env-vault"
                self.assertEqual(
                    save_capture.resolve_vault(None, workspace=workspace), "E:/env-vault"
                )
                self.assertEqual(
                    save_capture.resolve_vault("E:/cli-vault", workspace=workspace),
                    "E:/cli-vault",
                )

    def test_canonicalize_removes_tracking_and_sorts_query(self) -> None:
        actual = save_capture.canonicalize_url(
            "HTTPS://Example.COM/story/?utm_source=test&b=2&a=1#section"
        )
        self.assertEqual(actual, "https://example.com/story?a=1&b=2")

    def test_tavily_rejects_private_and_sensitive_urls(self) -> None:
        self.assertFalse(save_capture.is_safe_public_url_for_tavily("http://127.0.0.1/a")[0])
        self.assertFalse(
            save_capture.is_safe_public_url_for_tavily("https://example.com/a?token=secret")[0]
        )
        self.assertTrue(save_capture.is_safe_public_url_for_tavily("https://example.com/a")[0])

    def test_creates_utf8_note_and_detects_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            content_file = Path(temp_dir) / "capture.txt"
            content_file.write_text("Nội dung được giữ nguyên.", encoding="utf-8")
            args = make_args(temp_dir, content_file=str(content_file))

            first = save_capture.run_capture(args)
            self.assertEqual(first["status"], "created")
            note_path = Path(str(first["path"]))
            self.assertTrue(note_path.exists())
            note = note_path.read_text(encoding="utf-8")
            self.assertIn("canonical_url: \"https://example.com/story?a=1&b=2\"", note)
            self.assertIn("Nội dung được giữ nguyên.", note)

            second = save_capture.run_capture(args)
            self.assertEqual(second["status"], "duplicate")
            self.assertEqual(Path(str(second["path"])), note_path)

    def test_link_only_capture_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = save_capture.run_capture(
                make_args(temp_dir, title="Bookmark", content_type="bookmark")
            )
            self.assertTrue(result["link_only"])
            note = Path(str(result["path"])).read_text(encoding="utf-8")
            self.assertIn("link_only: true", note)
            self.assertIn("Link-only capture", note)

    def test_destination_cannot_escape_vault(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(save_capture.CaptureError):
                save_capture.run_capture(make_args(temp_dir, folder="../outside"))


if __name__ == "__main__":
    unittest.main()
