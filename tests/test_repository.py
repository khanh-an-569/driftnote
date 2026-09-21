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
        self.assertEqual(manifest["name"], "driftnote")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(manifest["skills"], "./skills/")

        expected_skill_names = (
            "web-to-obsidian",
            "obsidian-clip-beautifier",
            "obsidian-excalidraw-mindmap",
        )
        actual_skill_names = tuple(
            sorted(path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md"))
        )
        self.assertEqual(actual_skill_names, tuple(sorted(expected_skill_names)))

        for skill_name in expected_skill_names:
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

    def test_portable_manifest_matches_codex_compatibility_manifest(self) -> None:
        portable_path = ROOT / "plugin.json"
        self.assertTrue(portable_path.is_file(), "portable plugin.json is missing")
        portable = json.loads(portable_path.read_text(encoding="utf-8"))
        compatibility = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )

        self.assertEqual(
            portable.pop("$schema"),
            "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        )
        self.assertEqual(portable, compatibility)

    def test_architecture_docs_list_every_skill(self) -> None:
        skill_names = sorted(path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md"))
        self.assertTrue(skill_names)

        for doc_name in ("architecture.md", "architecture.vi.md"):
            text = (ROOT / "docs" / doc_name).read_text(encoding="utf-8")
            for skill_name in skill_names:
                self.assertIn(
                    f"### `{skill_name}`",
                    text,
                    f"{doc_name} is missing a component section for `{skill_name}`",
                )

    def test_plugin_interface_matches_the_installed_user_experience(self) -> None:
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        interface = manifest["interface"]
        prompts = interface["defaultPrompt"]

        self.assertLessEqual(len(prompts), 3)
        self.assertTrue(all(prompt and len(prompt) <= 128 for prompt in prompts))
        self.assertEqual(
            set(interface["capabilities"]),
            {
                "Browser context",
                "Local vault write",
                "Public web extraction",
                "Vault formatting setup",
                "Diagram export",
            },
        )

    def test_yaml_and_base_files_parse(self) -> None:
        paths = [
            ROOT / "driftnote.example.yaml",
            ROOT / "vault-starter" / "Web Inbox.base",
            ROOT / "skills" / "web-to-obsidian" / "agents" / "openai.yaml",
            ROOT / "skills" / "obsidian-clip-beautifier" / "agents" / "openai.yaml",
            ROOT / "skills" / "obsidian-excalidraw-mindmap" / "agents" / "openai.yaml",
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
        ignored_names = {".env", "driftnote.yaml"}
        for path in ROOT.rglob("*"):
            if (
                not path.is_file()
                or path.name in ignored_names
                or any(part in ignored_parts for part in path.parts)
            ):
                continue
            if path.suffix.lower() in {".pyc", ".png", ".jpg", ".jpeg", ".gif"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in secret_patterns:
                self.assertFalse(
                    bool(pattern.search(text)),
                    f"Secret-like value found in tracked source: {path}",
                )


if __name__ == "__main__":
    unittest.main()
