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


def make_two_level_outline() -> dict:
    return make_outline(
        layout="tree",
        nodes=[
            {
                "id": "a",
                "text": "Branch A",
                "action": "full",
                "source_anchor": None,
                "children": [
                    {"id": "a1", "text": "A1", "action": "full", "source_anchor": None, "children": []},
                    {"id": "a2", "text": "A2", "action": "full", "source_anchor": None, "children": []},
                ],
            },
            {
                "id": "b",
                "text": "Branch B",
                "action": "full",
                "source_anchor": None,
                "children": [],
            },
        ],
    )


class TreeLayoutTests(unittest.TestCase):
    def test_root_and_all_nodes_get_positions(self) -> None:
        outline = generate_excalidraw.validate_outline(make_two_level_outline())
        positions = generate_excalidraw.compute_tree_layout(outline)
        self.assertIn("__root__", positions)
        for node_id in ("a", "a1", "a2", "b"):
            self.assertIn(node_id, positions)

    def test_depth_increases_x_monotonically(self) -> None:
        outline = generate_excalidraw.validate_outline(make_two_level_outline())
        positions = generate_excalidraw.compute_tree_layout(outline)
        self.assertLess(positions["__root__"].x, positions["a"].x)
        self.assertLess(positions["a"].x, positions["a1"].x)

    def test_siblings_never_share_the_same_y(self) -> None:
        outline = generate_excalidraw.validate_outline(make_two_level_outline())
        positions = generate_excalidraw.compute_tree_layout(outline)
        self.assertNotEqual(positions["a1"].y, positions["a2"].y)
        self.assertNotEqual(positions["a"].y, positions["b"].y)


class RadialLayoutTests(unittest.TestCase):
    def test_root_is_at_the_origin(self) -> None:
        outline = generate_excalidraw.validate_outline(make_two_level_outline())
        positions = generate_excalidraw.compute_radial_layout(outline)
        self.assertEqual((positions["__root__"].x, positions["__root__"].y), (0.0, 0.0))

    def test_radius_grows_with_depth(self) -> None:
        import math

        outline = generate_excalidraw.validate_outline(make_two_level_outline())
        positions = generate_excalidraw.compute_radial_layout(outline)
        radius_a = math.hypot(positions["a"].x, positions["a"].y)
        radius_a1 = math.hypot(positions["a1"].x, positions["a1"].y)
        self.assertLess(radius_a, radius_a1)

    def test_siblings_land_at_distinct_angles(self) -> None:
        outline = generate_excalidraw.validate_outline(make_two_level_outline())
        positions = generate_excalidraw.compute_radial_layout(outline)
        self.assertNotEqual(
            (positions["a1"].x, positions["a1"].y),
            (positions["a2"].x, positions["a2"].y),
        )


class ElementBuilderTests(unittest.TestCase):
    def test_rectangle_carries_depth_color_and_binds_its_text(self) -> None:
        pos = generate_excalidraw.NodePosition(x=0, y=0)
        rect = generate_excalidraw.build_rectangle("n1", pos, depth=1, action="full")
        self.assertEqual(rect["type"], "rectangle")
        self.assertEqual(rect["strokeStyle"], "solid")
        self.assertEqual(rect["boundElements"], [{"id": "n1-text", "type": "text"}])

    def test_link_action_uses_dashed_stroke(self) -> None:
        pos = generate_excalidraw.NodePosition(x=0, y=0)
        rect = generate_excalidraw.build_rectangle("n1", pos, depth=1, action="link")
        self.assertEqual(rect["strokeStyle"], "dashed")

    def test_manual_action_uses_dotted_muted_style(self) -> None:
        pos = generate_excalidraw.NodePosition(x=0, y=0)
        rect = generate_excalidraw.build_rectangle("n1", pos, depth=1, action="manual")
        self.assertEqual(rect["strokeStyle"], "dotted")
        self.assertEqual(rect["backgroundColor"], "#f1f3f5")

    def test_text_is_bound_to_its_container(self) -> None:
        pos = generate_excalidraw.NodePosition(x=0, y=0)
        text_el = generate_excalidraw.build_text("n1-text", "n1", pos, "Hello")
        self.assertEqual(text_el["type"], "text")
        self.assertEqual(text_el["containerId"], "n1")
        self.assertEqual(text_el["text"], "Hello")
        self.assertEqual(text_el["fontFamily"], 1)

    def test_arrow_binds_start_and_end_elements(self) -> None:
        start = generate_excalidraw.NodePosition(x=0, y=0)
        end = generate_excalidraw.NodePosition(x=500, y=0)
        arrow = generate_excalidraw.build_arrow("root->n1", "root", "n1", start, end)
        self.assertEqual(arrow["type"], "arrow")
        self.assertEqual(arrow["startBinding"]["elementId"], "root")
        self.assertEqual(arrow["endBinding"]["elementId"], "n1")
        self.assertEqual(arrow["endArrowhead"], "triangle")

    def test_seeds_are_stable_across_calls(self) -> None:
        pos = generate_excalidraw.NodePosition(x=0, y=0)
        first = generate_excalidraw.build_rectangle("n1", pos, depth=1, action="full")
        second = generate_excalidraw.build_rectangle("n1", pos, depth=1, action="full")
        self.assertEqual(first["seed"], second["seed"])

    def test_obsidian_uri_encodes_vault_file_and_anchor(self) -> None:
        uri = generate_excalidraw.build_obsidian_uri(
            "Second Brain", "10 Sources/example.md", "some-heading"
        )
        self.assertTrue(uri.startswith("obsidian://open?"))
        self.assertIn("vault=Second+Brain", uri)
        self.assertIn("some-heading", uri)

    def test_obsidian_uri_without_anchor_omits_the_fragment(self) -> None:
        uri = generate_excalidraw.build_obsidian_uri("Second Brain", "10 Sources/example.md", None)
        self.assertNotIn("%23", uri)


if __name__ == "__main__":
    unittest.main()
