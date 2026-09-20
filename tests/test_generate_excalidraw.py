from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "obsidian-excalidraw-mindmap"
SCRIPT_PATH = SKILL_ROOT / "scripts" / "generate_excalidraw.py"

SPEC = importlib.util.spec_from_file_location("generate_excalidraw", SCRIPT_PATH)
assert SPEC and SPEC.loader
generate_excalidraw = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = generate_excalidraw
SPEC.loader.exec_module(generate_excalidraw)


def make_outline(**overrides: object) -> dict:
    outline = {
        "title": "Test Note",
        "source_note_path": "10 Sources/test-note.md",
        "layout": "tree",
        "long_content_strategy": "condense",
        "nodes": [
            {
                "id": "n1",
                "text": "Main idea 1",
                "action": "full",
                "source_anchor": None,
                "children": [],
            }
        ],
    }
    outline.update(overrides)
    return outline


class ValidateOutlineTests(unittest.TestCase):
    def test_valid_outline_builds_a_tree_of_nodes(self) -> None:
        outline = generate_excalidraw.validate_outline(make_outline())
        self.assertEqual(outline.title, "Test Note")
        self.assertEqual(len(outline.nodes), 1)
        self.assertEqual(outline.nodes[0].id, "n1")
        self.assertEqual(outline.nodes[0].depth, 1)

    def test_nested_children_get_increasing_depth(self) -> None:
        outline = make_outline(
            nodes=[
                {
                    "id": "n1",
                    "text": "Parent",
                    "action": "full",
                    "source_anchor": None,
                    "children": [
                        {
                            "id": "n1-1",
                            "text": "Child",
                            "action": "full",
                            "source_anchor": None,
                            "children": [],
                        }
                    ],
                }
            ]
        )
        result = generate_excalidraw.validate_outline(outline)
        self.assertEqual(result.nodes[0].depth, 1)
        self.assertEqual(result.nodes[0].children[0].depth, 2)

    def test_duplicate_ids_are_rejected(self) -> None:
        outline = make_outline(
            nodes=[
                {"id": "n1", "text": "A", "action": "full", "source_anchor": None, "children": []},
                {"id": "n1", "text": "B", "action": "full", "source_anchor": None, "children": []},
            ]
        )
        with self.assertRaises(generate_excalidraw.MindmapError):
            generate_excalidraw.validate_outline(outline)

    def test_non_full_action_requires_source_anchor(self) -> None:
        outline = make_outline(
            nodes=[
                {
                    "id": "n1",
                    "text": "Needs link",
                    "action": "link",
                    "source_anchor": None,
                    "children": [],
                }
            ]
        )
        with self.assertRaises(generate_excalidraw.MindmapError):
            generate_excalidraw.validate_outline(outline)

    def test_text_over_the_action_limit_is_rejected(self) -> None:
        outline = make_outline(
            nodes=[
                {
                    "id": "n1",
                    "text": "x" * 100,
                    "action": "full",
                    "source_anchor": None,
                    "children": [],
                }
            ]
        )
        with self.assertRaises(generate_excalidraw.MindmapError):
            generate_excalidraw.validate_outline(outline)

    def test_depth_beyond_the_maximum_is_rejected(self) -> None:
        node = {"id": "n6", "text": "Too deep", "action": "full", "source_anchor": None, "children": []}
        for index in range(5, 0, -1):
            node = {
                "id": f"n{index}",
                "text": f"Level {index}",
                "action": "full",
                "source_anchor": None,
                "children": [node],
            }
        with self.assertRaises(generate_excalidraw.MindmapError):
            generate_excalidraw.validate_outline(make_outline(nodes=[node]))

    def test_invalid_layout_is_rejected(self) -> None:
        with self.assertRaises(generate_excalidraw.MindmapError):
            generate_excalidraw.validate_outline(make_outline(layout="circular"))


if __name__ == "__main__":
    unittest.main()
