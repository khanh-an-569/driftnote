from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "obsidian-clip-beautifier"
SCRIPT_PATH = SKILL_ROOT / "scripts" / "prepare_clip_pipeline.py"

SPEC = importlib.util.spec_from_file_location("prepare_clip_pipeline", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ObsidianClipBeautifierTests(unittest.TestCase):
    def make_vault(self, root: Path) -> Path:
        vault = root / "Vault"
        (vault / ".obsidian").mkdir(parents=True)
        return vault

    def test_assets_are_valid_and_scoped(self) -> None:
        template = json.loads(
            (SKILL_ROOT / "assets" / "web-clip-clean-reading-clipper.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(template["schemaVersion"], "0.1.0")
        self.assertEqual(template["path"], "00 Inbox/Web")
        properties = {item["name"]: item for item in template["properties"]}
        self.assertEqual(properties["status"]["value"], "inbox")
        self.assertEqual(properties["cssclasses"]["value"], "web-clip")

        css = (SKILL_ROOT / "assets" / "obsidian-clip-beautifier.css").read_text(
            encoding="utf-8"
        )
        selectors = [line.strip() for line in css.splitlines() if line.strip().endswith("{")]
        self.assertTrue(selectors)
        self.assertTrue(all(".web-clip" in selector for selector in selectors))

    def test_preview_makes_no_changes_and_apply_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            vault = self.make_vault(Path(temporary))

            preview = MODULE.prepare(vault, apply=False)
            self.assertTrue(all(item["status"] == "planned" for item in preview["files"]))
            self.assertFalse((vault / "00 Inbox").exists())

            applied = MODULE.prepare(vault, apply=True)
            self.assertTrue(all(item["status"] == "created" for item in applied["files"]))

            repeated = MODULE.prepare(vault, apply=True)
            self.assertTrue(all(item["status"] == "unchanged" for item in repeated["files"]))

    def test_apply_never_overwrites_a_conflicting_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            vault = self.make_vault(Path(temporary))
            target = vault / ".obsidian" / "snippets" / "obsidian-clip-beautifier.css"
            target.parent.mkdir(parents=True)
            target.write_text("/* user customization */\n", encoding="utf-8")

            result = MODULE.prepare(vault, apply=True)
            css_item = next(item for item in result["files"] if item["path"] == str(target))
            self.assertEqual(css_item["status"], "conflict")
            self.assertEqual(target.read_text(encoding="utf-8"), "/* user customization */\n")


if __name__ == "__main__":
    unittest.main()
