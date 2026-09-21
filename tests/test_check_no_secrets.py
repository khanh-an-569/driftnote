from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_no_secrets.py"


def run_scan(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        check=False,
        encoding="utf-8",
    )


class SecretScanTests(unittest.TestCase):
    def test_clean_tree_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "config.example").write_text(
                "TAVILY_API_KEY=\nVAULT_PATH=D:/Notes/Example\n",
                encoding="utf-8",
            )

            result = run_scan(root)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("No high-confidence secrets", result.stdout)

    def test_secret_is_reported_without_echoing_its_value(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fake_token = "ghp_" + ("A" * 36)
            (root / "leaked.txt").write_text(fake_token, encoding="utf-8")

            result = run_scan(root)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("github-token", result.stdout)
            self.assertIn("leaked.txt:1", result.stdout)
            self.assertNotIn(fake_token, result.stdout)
            self.assertNotIn(fake_token, result.stderr)

    def test_personal_windows_profile_path_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            personal_path = "C:" + "\\Users\\Alice\\Obsidian Vault"
            (root / "settings.txt").write_text(personal_path, encoding="utf-8")

            result = run_scan(root)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("personal-windows-user-path", result.stdout)
            self.assertNotIn("Alice", result.stdout)


if __name__ == "__main__":
    unittest.main()
