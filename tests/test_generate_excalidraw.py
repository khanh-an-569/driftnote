from __future__ import annotations

import importlib.util
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


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

    def test_node_id_ending_in_text_suffix_is_rejected(self) -> None:
        outline = make_outline(
            nodes=[
                {
                    "id": "n1-text",
                    "text": "Would collide with n1's text element id",
                    "action": "full",
                    "source_anchor": None,
                    "children": [],
                }
            ]
        )
        with self.assertRaises(generate_excalidraw.MindmapError):
            generate_excalidraw.validate_outline(outline)

    def test_reserved_root_node_id_is_rejected(self) -> None:
        outline = make_outline(
            nodes=[
                {
                    "id": "root",
                    "text": "Would collide with reserved root node id",
                    "action": "full",
                    "source_anchor": None,
                    "children": [],
                }
            ]
        )
        with self.assertRaises(generate_excalidraw.MindmapError):
            generate_excalidraw.validate_outline(outline)

    def test_node_id_containing_arrow_separator_is_rejected(self) -> None:
        outline = make_outline(
            nodes=[
                {
                    "id": "a->b",
                    "text": "Would collide with arrow-id naming convention",
                    "action": "full",
                    "source_anchor": None,
                    "children": [],
                }
            ]
        )
        with self.assertRaises(generate_excalidraw.MindmapError):
            generate_excalidraw.validate_outline(outline)


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


def _boxes_overlap(pos_a, pos_b) -> bool:
    """Return True if two NodePosition bounding boxes overlap (share interior area)."""
    ax0, ay0 = pos_a.x, pos_a.y
    ax1, ay1 = pos_a.x + pos_a.width, pos_a.y + pos_a.height
    bx0, by0 = pos_b.x, pos_b.y
    bx1, by1 = pos_b.x + pos_b.width, pos_b.y + pos_b.height
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def make_wide_fanout_outline(leaf_count: int) -> dict:
    return make_outline(
        layout="radial",
        nodes=[
            {
                "id": f"leaf{i}",
                "text": f"Leaf {i}",
                "action": "full",
                "source_anchor": None,
                "children": [],
            }
            for i in range(leaf_count)
        ],
    )


class RadialLayoutTests(unittest.TestCase):
    def test_root_is_centered_on_the_origin(self) -> None:
        outline = generate_excalidraw.validate_outline(make_two_level_outline())
        positions = generate_excalidraw.compute_radial_layout(outline)
        root = positions["__root__"]
        self.assertEqual(
            (root.x, root.y),
            (0.0 - generate_excalidraw.NODE_WIDTH / 2, 0.0 - generate_excalidraw.NODE_HEIGHT / 2),
        )

    def test_radius_grows_with_depth(self) -> None:
        outline = generate_excalidraw.validate_outline(make_two_level_outline())
        positions = generate_excalidraw.compute_radial_layout(outline)
        root = positions["__root__"]
        center_a_x = positions["a"].x + generate_excalidraw.NODE_WIDTH / 2
        center_a_y = positions["a"].y + generate_excalidraw.NODE_HEIGHT / 2
        center_a1_x = positions["a1"].x + generate_excalidraw.NODE_WIDTH / 2
        center_a1_y = positions["a1"].y + generate_excalidraw.NODE_HEIGHT / 2
        root_center_x = root.x + generate_excalidraw.NODE_WIDTH / 2
        root_center_y = root.y + generate_excalidraw.NODE_HEIGHT / 2
        radius_a = math.hypot(center_a_x - root_center_x, center_a_y - root_center_y)
        radius_a1 = math.hypot(center_a1_x - root_center_x, center_a1_y - root_center_y)
        self.assertLess(radius_a, radius_a1)

    def test_siblings_land_at_distinct_angles(self) -> None:
        outline = generate_excalidraw.validate_outline(make_two_level_outline())
        positions = generate_excalidraw.compute_radial_layout(outline)
        self.assertNotEqual(
            (positions["a1"].x, positions["a1"].y),
            (positions["a2"].x, positions["a2"].y),
        )

    def test_wide_fanout_does_not_overlap(self) -> None:
        outline = generate_excalidraw.validate_outline(make_wide_fanout_outline(9))
        positions = generate_excalidraw.compute_radial_layout(outline)
        leaf_positions = [positions[f"leaf{i}"] for i in range(9)]
        for i in range(len(leaf_positions)):
            for j in range(i + 1, len(leaf_positions)):
                self.assertFalse(
                    _boxes_overlap(leaf_positions[i], leaf_positions[j]),
                    f"leaf{i} and leaf{j} bounding boxes overlap",
                )


class ElementBuilderTests(unittest.TestCase):
    def test_rectangle_carries_depth_color_and_binds_its_text(self) -> None:
        pos = generate_excalidraw.NodePosition(x=0, y=0)
        rect = generate_excalidraw.build_rectangle("n1", pos, depth=1, action="full")
        self.assertEqual(rect["type"], "rectangle")
        self.assertEqual(rect["strokeStyle"], "solid")
        self.assertEqual(rect["boundElements"], [{"id": "n1-text", "type": "text"}])

    def test_root_depth_color_is_readable_against_white_background_and_text(self) -> None:
        # Depth 0 (the root) must not be the old near-black-fill / white-stroke pair,
        # which was invisible against the white canvas and unreadable under the
        # text element's hardcoded dark strokeColor.
        background, stroke = generate_excalidraw.DEPTH_COLORS[0]
        self.assertNotEqual(background, "#1e1e2e")
        self.assertNotEqual(stroke, "#ffffff")
        # The text's hardcoded strokeColor must contrast with the root's background.
        text_stroke_color = "#1e1e2e"
        self.assertNotEqual(background, text_stroke_color)

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
        # Spaces must be percent-encoded as %20, not '+' (which is not the
        # documented obsidian:// URI format).
        self.assertIn("vault=Second%20Brain", uri)
        self.assertNotIn("+", uri)
        self.assertIn("some-heading", uri)

    def test_obsidian_uri_without_anchor_omits_the_fragment(self) -> None:
        uri = generate_excalidraw.build_obsidian_uri("Second Brain", "10 Sources/example.md", None)
        self.assertNotIn("%23", uri)


class DocumentAssemblyTests(unittest.TestCase):
    def test_document_has_the_excalidraw_envelope(self) -> None:
        outline = generate_excalidraw.validate_outline(make_two_level_outline())
        positions = generate_excalidraw.compute_tree_layout(outline)
        document = generate_excalidraw.build_excalidraw_document(
            outline, positions, vault_name="Second Brain"
        )
        self.assertEqual(document["type"], "excalidraw")
        self.assertIn("elements", document)

    def test_every_node_produces_a_rectangle_text_and_arrow(self) -> None:
        outline = generate_excalidraw.validate_outline(make_two_level_outline())
        positions = generate_excalidraw.compute_tree_layout(outline)
        document = generate_excalidraw.build_excalidraw_document(
            outline, positions, vault_name="Second Brain"
        )
        rect_ids = {el["id"] for el in document["elements"] if el["type"] == "rectangle"}
        self.assertEqual(rect_ids, {"root", "a", "a1", "a2", "b"})
        arrow_count = sum(1 for el in document["elements"] if el["type"] == "arrow")
        self.assertEqual(arrow_count, 4)

    def test_parent_and_child_rectangles_both_list_their_arrow_in_bound_elements(self) -> None:
        outline = generate_excalidraw.validate_outline(make_two_level_outline())
        positions = generate_excalidraw.compute_tree_layout(outline)
        document = generate_excalidraw.build_excalidraw_document(
            outline, positions, vault_name="Second Brain"
        )
        elements_by_id = {el["id"]: el for el in document["elements"]}
        arrow_id = "root->a"
        self.assertIn(arrow_id, elements_by_id)

        root_rect = elements_by_id["root"]
        child_rect = elements_by_id["a"]
        self.assertIn({"id": arrow_id, "type": "arrow"}, root_rect["boundElements"])
        self.assertIn({"id": arrow_id, "type": "arrow"}, child_rect["boundElements"])

        # The rectangle's own text binding must still be present alongside the arrow.
        self.assertIn({"id": "a-text", "type": "text"}, child_rect["boundElements"])

    def test_link_action_nodes_carry_an_obsidian_link(self) -> None:
        outline_data = make_outline(
            layout="tree",
            long_content_strategy="link",
            nodes=[
                {
                    "id": "n1",
                    "text": "See note",
                    "action": "link",
                    "source_anchor": "some-heading",
                    "children": [],
                }
            ],
        )
        outline = generate_excalidraw.validate_outline(outline_data)
        positions = generate_excalidraw.compute_tree_layout(outline)
        document = generate_excalidraw.build_excalidraw_document(
            outline, positions, vault_name="Second Brain"
        )
        rect = next(el for el in document["elements"] if el["id"] == "n1")
        self.assertTrue(rect["link"].startswith("obsidian://open?"))


class PublishTests(unittest.TestCase):
    def test_write_creates_a_new_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "diagram.excalidraw"
            status = generate_excalidraw.write_excalidraw_file({"type": "excalidraw"}, target, regenerate=False)
            self.assertEqual(status, "created")
            self.assertTrue(target.exists())

    def test_write_refuses_to_clobber_without_regenerate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "diagram.excalidraw"
            generate_excalidraw.write_excalidraw_file({"type": "excalidraw"}, target, regenerate=False)
            with self.assertRaises(generate_excalidraw.MindmapError):
                generate_excalidraw.write_excalidraw_file({"type": "excalidraw"}, target, regenerate=False)

    def test_write_with_regenerate_overwrites_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "diagram.excalidraw"
            generate_excalidraw.write_excalidraw_file({"version": 1}, target, regenerate=False)
            status = generate_excalidraw.write_excalidraw_file({"version": 2}, target, regenerate=True)
            self.assertEqual(status, "regenerated")
            self.assertIn('"version": 2', target.read_text(encoding="utf-8"))

    def test_write_cleans_up_temp_file_on_mid_write_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "diagram.excalidraw"
            with mock.patch.object(
                generate_excalidraw.os, "fsync", side_effect=OSError("disk full")
            ):
                with self.assertRaises(OSError):
                    generate_excalidraw.write_excalidraw_file(
                        {"type": "excalidraw"}, target, regenerate=False
                    )
            self.assertFalse(target.exists())
            leftover_temp_files = list(target.parent.glob("*.tmp"))
            self.assertEqual(leftover_temp_files, [])

    def test_write_raises_clear_error_when_hard_links_are_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "diagram.excalidraw"
            with mock.patch.object(
                generate_excalidraw.os,
                "link",
                side_effect=OSError("hard links not supported on this filesystem"),
            ):
                with self.assertRaises(generate_excalidraw.MindmapError) as ctx:
                    generate_excalidraw.write_excalidraw_file(
                        {"type": "excalidraw"}, target, regenerate=False
                    )
            # Must be a distinct message from the "already exists" case.
            self.assertNotIn("already exists", str(ctx.exception))

    def test_append_diagram_link_adds_a_new_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            note = Path(temp_dir) / "note.md"
            note.write_text("# Title\n\nBody text.\n", encoding="utf-8")
            changed = generate_excalidraw.append_diagram_link(note, "note.excalidraw")
            self.assertTrue(changed)
            text = note.read_text(encoding="utf-8")
            self.assertIn("## Sơ đồ Excalidraw", text)
            self.assertIn("![[note.excalidraw]]", text)

    def test_append_diagram_link_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            note = Path(temp_dir) / "note.md"
            note.write_text("# Title\n\nBody text.\n", encoding="utf-8")
            generate_excalidraw.append_diagram_link(note, "note.excalidraw")
            first_text = note.read_text(encoding="utf-8")
            changed_again = generate_excalidraw.append_diagram_link(note, "note.excalidraw")
            self.assertFalse(changed_again)
            self.assertEqual(note.read_text(encoding="utf-8"), first_text)

    def test_append_diagram_link_never_touches_existing_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            note = Path(temp_dir) / "note.md"
            original = "---\nsource_id: abc123\n---\n\n# Title\n\n## Ghi chú của tôi\n\nMy note.\n"
            note.write_text(original, encoding="utf-8")
            generate_excalidraw.append_diagram_link(note, "note.excalidraw")
            text = note.read_text(encoding="utf-8")
            self.assertTrue(text.startswith(original))


class CliTests(unittest.TestCase):
    def make_vault_with_note(self, root: Path) -> tuple[Path, Path]:
        vault = root / "Vault"
        note_dir = vault / "10 Sources"
        note_dir.mkdir(parents=True)
        note_path = note_dir / "test-note.md"
        note_path.write_text("# Test Note\n\nSome content.\n", encoding="utf-8")
        return vault, note_path

    def make_outline_file(self, root: Path, source_note_path: str) -> Path:
        outline_path = root / "outline.json"
        outline_path.write_text(
            json.dumps(
                {
                    "title": "Test Note",
                    "source_note_path": source_note_path,
                    "layout": "tree",
                    "long_content_strategy": "condense",
                    "nodes": [
                        {
                            "id": "n1",
                            "text": "Main idea",
                            "action": "full",
                            "source_anchor": None,
                            "children": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return outline_path

    def test_resolve_vault_requires_an_existing_directory(self) -> None:
        with self.assertRaises(generate_excalidraw.MindmapError):
            generate_excalidraw.resolve_vault("Z:/does/not/exist")

    def test_run_creates_diagram_and_links_the_note(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vault, note_path = self.make_vault_with_note(root)
            outline_path = self.make_outline_file(root, "10 Sources/test-note.md")

            args = generate_excalidraw.build_parser().parse_args(
                ["--outline-file", str(outline_path), "--vault", str(vault)]
            )
            result = generate_excalidraw.run(args)

            self.assertEqual(result["status"], "created")
            self.assertTrue(Path(result["path"]).exists())
            self.assertTrue(result["linked_from_note"])
            self.assertIn("![[test-note.excalidraw]]", note_path.read_text(encoding="utf-8"))

    def test_main_reports_errors_as_json_on_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outline_path = root / "missing-fields.json"
            outline_path.write_text("{}", encoding="utf-8")
            exit_code = generate_excalidraw.main(
                ["--outline-file", str(outline_path), "--vault", str(root)]
            )
            self.assertEqual(exit_code, 1)

    def test_run_uses_output_dir_from_an_explicit_config_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vault, _note_path = self.make_vault_with_note(root)
            outline_path = self.make_outline_file(root, "10 Sources/test-note.md")
            config_path = root / "driftnote.yaml"
            config_path.write_text(
                'vault_root: "unused"\nexcalidraw_output_dir: "20 Knowledge/Excalidraw"\n',
                encoding="utf-8",
            )

            args = generate_excalidraw.build_parser().parse_args(
                [
                    "--outline-file",
                    str(outline_path),
                    "--vault",
                    str(vault),
                    "--config-file",
                    str(config_path),
                ]
            )
            result = generate_excalidraw.run(args)

            expected_path = vault.resolve() / "20 Knowledge" / "Excalidraw" / "test-note.excalidraw"
            self.assertEqual(Path(result["path"]), expected_path)
            self.assertTrue(expected_path.exists())

    def test_run_ignores_config_file_when_output_dir_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vault, _note_path = self.make_vault_with_note(root)
            outline_path = self.make_outline_file(root, "10 Sources/test-note.md")
            config_path = root / "driftnote.yaml"
            config_path.write_text('excalidraw_output_dir: "should-not-be-used"\n', encoding="utf-8")

            args = generate_excalidraw.build_parser().parse_args(
                [
                    "--outline-file",
                    str(outline_path),
                    "--vault",
                    str(vault),
                    "--config-file",
                    str(config_path),
                    "--output-dir",
                    "explicit-dir",
                ]
            )
            result = generate_excalidraw.run(args)
            self.assertEqual(
                Path(result["path"]), vault.resolve() / "explicit-dir" / "test-note.excalidraw"
            )

    def test_run_rejects_a_source_note_outside_the_vault(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vault, _note_path = self.make_vault_with_note(root)
            outside_note = root / "outside.md"
            outside_note.write_text("# Outside\n", encoding="utf-8")
            outline_path = self.make_outline_file(root, "../outside.md")

            args = generate_excalidraw.build_parser().parse_args(
                ["--outline-file", str(outline_path), "--vault", str(vault)]
            )
            with self.assertRaises(generate_excalidraw.MindmapError) as ctx:
                generate_excalidraw.run(args)
            self.assertIn("must be inside the vault", str(ctx.exception))

    def test_run_rejects_an_output_dir_outside_the_vault(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vault, _note_path = self.make_vault_with_note(root)
            outline_path = self.make_outline_file(root, "10 Sources/test-note.md")

            args = generate_excalidraw.build_parser().parse_args(
                [
                    "--outline-file",
                    str(outline_path),
                    "--vault",
                    str(vault),
                    "--output-dir",
                    "../outside-output",
                ]
            )
            with self.assertRaises(generate_excalidraw.MindmapError) as ctx:
                generate_excalidraw.run(args)
            self.assertIn("must be inside the vault", str(ctx.exception))

    def test_export_dir_respects_no_clobber_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vault, _note_path = self.make_vault_with_note(root)
            outline_path = self.make_outline_file(root, "10 Sources/test-note.md")
            export_dir = root / "exports"
            export_dir.mkdir()
            existing_export = export_dir / "test-note.excalidraw"
            existing_export.write_text("pre-existing content", encoding="utf-8")

            args = generate_excalidraw.build_parser().parse_args(
                [
                    "--outline-file",
                    str(outline_path),
                    "--vault",
                    str(vault),
                    "--export-dir",
                    str(export_dir),
                ]
            )
            result = generate_excalidraw.run(args)

            # The main vault write must still succeed even though the export
            # copy could not be written without clobbering.
            self.assertEqual(result["status"], "created")
            self.assertTrue(Path(result["path"]).exists())
            self.assertIsNone(result["exported_to"])
            self.assertIsNotNone(result["export_error"])
            self.assertIn("already exists", result["export_error"])
            self.assertEqual(existing_export.read_text(encoding="utf-8"), "pre-existing content")

    @unittest.skipUnless(sys.platform == "win32", "invalid path component is Windows-specific")
    def test_export_dir_failure_does_not_fail_the_whole_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vault, note_path = self.make_vault_with_note(root)
            outline_path = self.make_outline_file(root, "10 Sources/test-note.md")
            # '?' is not a legal character in a Windows path component, so this
            # directory can never be created.
            export_dir = root / "bad?export"

            args = generate_excalidraw.build_parser().parse_args(
                [
                    "--outline-file",
                    str(outline_path),
                    "--vault",
                    str(vault),
                    "--export-dir",
                    str(export_dir),
                ]
            )
            result = generate_excalidraw.run(args)

            self.assertEqual(result["status"], "created")
            self.assertTrue(Path(result["path"]).exists())
            self.assertTrue(result["linked_from_note"])
            self.assertIn("![[test-note.excalidraw]]", note_path.read_text(encoding="utf-8"))
            self.assertIsNone(result["exported_to"])
            self.assertIsNotNone(result["export_error"])


if __name__ == "__main__":
    unittest.main()
