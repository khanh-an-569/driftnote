from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class RepositoryTests(unittest.TestCase):
    def test_manifest_and_skill_metadata(self) -> None:
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "web-to-obsidian")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(manifest["skills"], "./skills/")

        for skill_name in ("web-to-obsidian", "obsidian-inbox-processor"):
            skill_text = (ROOT / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
            self.assertTrue(skill_text.startswith("---\n"))
            frontmatter = skill_text.split("---", 2)[1]
            metadata = yaml.safe_load(frontmatter)
            self.assertEqual(metadata["name"], skill_name)
            self.assertTrue(metadata["description"])

            ui = yaml.safe_load(
                (ROOT / "skills" / skill_name / "agents" / "openai.yaml").read_text(encoding="utf-8")
            )
            self.assertIn(f"${skill_name}", ui["interface"]["default_prompt"])

    def test_yaml_and_base_files_parse(self) -> None:
        paths = [
            ROOT / "web-to-obsidian.example.yaml",
            ROOT / "vault-starter" / "Web Inbox.base",
            ROOT / "skills" / "web-to-obsidian" / "agents" / "openai.yaml",
            ROOT / "skills" / "obsidian-inbox-processor" / "agents" / "openai.yaml",
        ]
        parsed = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in paths]
        base = parsed[1]
        self.assertEqual(
            [view["name"] for view in base["views"]],
            ["Inbox", "Reading", "Music", "Processed"],
        )

    def test_repository_contains_no_obvious_secret(self) -> None:
        secret_patterns = [
            re.compile(r"tvly-[A-Za-z0-9_-]{8,}"),
            re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
        ]
        ignored_parts = {".git", "__pycache__"}
        for path in ROOT.rglob("*"):
            if not path.is_file() or any(part in ignored_parts for part in path.parts):
                continue
            if path.suffix.lower() in {".pyc", ".png", ".jpg", ".jpeg", ".gif"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in secret_patterns:
                self.assertIsNone(pattern.search(text), f"Secret-like value found in {path}")


if __name__ == "__main__":
    unittest.main()
