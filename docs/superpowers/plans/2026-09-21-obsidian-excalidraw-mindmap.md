# Obsidian Excalidraw Mindmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new `obsidian-excalidraw-mindmap` skill that turns a captured Obsidian note into a polished, branching Excalidraw diagram (radial mindmap or hierarchical tree), published in-vault and optionally standalone, offered as an optional follow-up right after `web-to-obsidian` captures a note.

**Architecture:** Claude builds a strictly-source-derived "outline" JSON (per `references/outline-schema.md`); a new stdlib-only script `skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py` validates that outline, computes a deterministic collision-avoiding layout (radial or tree), builds native Excalidraw elements (color-by-depth, hand-drawn style), and publishes the `.excalidraw` file atomically with no-clobber semantics, appending an idempotent embed link to the source note.

**Tech Stack:** Python 3 standard library only (`argparse`, `dataclasses`, `json`, `math`, `os`, `re`, `sys`, `tempfile`, `urllib.parse`, `zlib`, `pathlib`), `unittest` for tests (matching the repo's existing test runner — no `pytest` dependency).

**Spec:** `docs/superpowers/specs/2026-09-21-obsidian-excalidraw-mindmap-design.md`

## Global Constraints

- Stdlib-only implementation script — no new entries in `requirements-dev.txt` (mirrors `save_capture.py`'s "uses only the Python standard library" rule).
- Max outline tree depth: 5, counting a top-level node (direct child of the implicit root) as depth 1.
- Per-action node text length limits: `full` ≤ 80 chars, `condensed` ≤ 60 chars, `link` ≤ 40 chars, `manual` ≤ 40 chars.
- `long_content_strategy` is chosen once per run and applied consistently; the script never silently mixes `link`/`condense`/`manual` handling within one diagram (validation only enforces per-node `action` validity — the *consistency* of strategy choice is a Claude-side/SKILL.md responsibility, not a script-enforced invariant, since the script only ever sees the final per-node `action` values).
- All file writes are atomic (temp file + `fsync` + `os.replace`/`os.link`) and no-clobber by default; overwriting an existing `.excalidraw` file requires an explicit `--regenerate` flag.
- The source note's frontmatter and `Ghi chú của tôi` section are never modified; the skill only appends a new, idempotent `## Sơ đồ Excalidraw` section.
- `plugin.json` (root) and `.codex-plugin/plugin.json` must remain byte-identical except for root's extra `$schema` key (enforced by `tests/test_repository.py::test_portable_manifest_matches_codex_compatibility_manifest`).
- `interface.defaultPrompt` in those manifests must stay at length ≤ 3, each entry ≤ 128 chars (enforced by `tests/test_repository.py::test_plugin_interface_matches_the_installed_user_experience`).
- Do not modify `README.md` or `README.vi.md` — both already have unrelated uncommitted changes in the working tree; leave them for the user.
- Do not modify `.env` or `web-to-obsidian.yaml` (local, gitignored) — only the `.example` templates.

---

### Task 1: Outline validation

**Files:**
- Create: `skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py`
- Test: `tests/test_generate_excalidraw.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `class MindmapError(RuntimeError)`
  - `@dataclass class OutlineNode: id: str; text: str; action: str; source_anchor: str | None; depth: int; children: list["OutlineNode"]`
  - `@dataclass class ValidatedOutline: title: str; source_note_path: str; layout: str; long_content_strategy: str; nodes: list[OutlineNode]`
  - `VALID_ACTIONS = ("full", "condensed", "link", "manual")`
  - `VALID_LAYOUTS = ("radial", "tree")`
  - `VALID_STRATEGIES = ("link", "condense", "manual")`
  - `MAX_TREE_DEPTH = 5`
  - `TEXT_LENGTH_LIMITS = {"full": 80, "condensed": 60, "link": 40, "manual": 40}`
  - `def validate_outline(data: dict) -> ValidatedOutline`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_generate_excalidraw.py`:

```python
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "obsidian-excalidraw-mindmap"
SCRIPT_PATH = SKILL_ROOT / "scripts" / "generate_excalidraw.py"

SPEC = importlib.util.spec_from_file_location("generate_excalidraw", SCRIPT_PATH)
assert SPEC and SPEC.loader
generate_excalidraw = importlib.util.module_from_spec(SPEC)
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_generate_excalidraw -v`
Expected: `ModuleNotFoundError`/`FileNotFoundError` or import failure, since `generate_excalidraw.py` does not exist yet.

- [ ] **Step 3: Create the script with validation logic**

Create `skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py`:

```python
#!/usr/bin/env python3
"""Turn a strictly source-derived outline into a brainstorm-style Excalidraw diagram."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class MindmapError(RuntimeError):
    """Raised when an outline, config, or CLI invocation is invalid."""


VALID_ACTIONS = ("full", "condensed", "link", "manual")
VALID_LAYOUTS = ("radial", "tree")
VALID_STRATEGIES = ("link", "condense", "manual")
MAX_TREE_DEPTH = 5
TEXT_LENGTH_LIMITS = {"full": 80, "condensed": 60, "link": 40, "manual": 40}


@dataclass
class OutlineNode:
    id: str
    text: str
    action: str
    source_anchor: str | None
    depth: int
    children: list["OutlineNode"] = field(default_factory=list)


@dataclass
class ValidatedOutline:
    title: str
    source_note_path: str
    layout: str
    long_content_strategy: str
    nodes: list[OutlineNode]


def validate_outline(data: dict[str, Any]) -> ValidatedOutline:
    if not isinstance(data, dict):
        raise MindmapError("Outline must be a JSON object.")

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        raise MindmapError("Outline is missing a non-empty 'title'.")

    source_note_path = data.get("source_note_path")
    if not isinstance(source_note_path, str) or not source_note_path.strip():
        raise MindmapError("Outline is missing a non-empty 'source_note_path'.")

    layout = data.get("layout")
    if layout not in VALID_LAYOUTS:
        raise MindmapError(f"'layout' must be one of {VALID_LAYOUTS}, got {layout!r}.")

    strategy = data.get("long_content_strategy")
    if strategy not in VALID_STRATEGIES:
        raise MindmapError(
            f"'long_content_strategy' must be one of {VALID_STRATEGIES}, got {strategy!r}."
        )

    raw_nodes = data.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise MindmapError("Outline must have a non-empty 'nodes' list.")

    seen_ids: set[str] = set()

    def build_node(raw: Any, depth: int) -> OutlineNode:
        if depth > MAX_TREE_DEPTH:
            raise MindmapError(
                f"A node exceeds the max depth of {MAX_TREE_DEPTH}. "
                "Use action 'link' instead of splitting further."
            )
        if not isinstance(raw, dict):
            raise MindmapError(f"Each node must be a JSON object (depth {depth}).")

        node_id = raw.get("id")
        if not isinstance(node_id, str) or not node_id.strip():
            raise MindmapError(f"Node at depth {depth} is missing a non-empty 'id'.")
        if node_id in seen_ids:
            raise MindmapError(f"Duplicate node id: {node_id!r}.")
        seen_ids.add(node_id)

        text = raw.get("text")
        if not isinstance(text, str) or not text.strip():
            raise MindmapError(f"Node {node_id!r} is missing non-empty 'text'.")

        action = raw.get("action")
        if action not in VALID_ACTIONS:
            raise MindmapError(
                f"Node {node_id!r} has invalid action {action!r}; must be one of {VALID_ACTIONS}."
            )

        limit = TEXT_LENGTH_LIMITS[action]
        if len(text) > limit:
            raise MindmapError(
                f"Node {node_id!r} text exceeds the {limit}-character limit for action "
                f"{action!r} ({len(text)} chars). Split it into child nodes or use action 'link'."
            )

        source_anchor = raw.get("source_anchor")
        if action != "full":
            if not isinstance(source_anchor, str) or not source_anchor.strip():
                raise MindmapError(
                    f"Node {node_id!r} has action {action!r} and requires a non-empty "
                    "'source_anchor'."
                )
        elif source_anchor is not None and not isinstance(source_anchor, str):
            raise MindmapError(f"Node {node_id!r} has a non-string 'source_anchor'.")

        raw_children = raw.get("children", [])
        if not isinstance(raw_children, list):
            raise MindmapError(f"Node {node_id!r} has a non-list 'children'.")
        children = [build_node(child, depth + 1) for child in raw_children]

        return OutlineNode(
            id=node_id,
            text=text,
            action=action,
            source_anchor=source_anchor,
            depth=depth,
            children=children,
        )

    nodes = [build_node(raw, 1) for raw in raw_nodes]

    return ValidatedOutline(
        title=title,
        source_note_path=source_note_path,
        layout=layout,
        long_content_strategy=strategy,
        nodes=nodes,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_generate_excalidraw -v`
Expected: `OK` (7 tests pass).

- [ ] **Step 5: Commit**

```bash
git add skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py tests/test_generate_excalidraw.py
git commit -m "feat: validate the outline JSON contract for the Excalidraw mindmap skill"
```

---

### Task 2: Layout algorithms (tree + radial)

**Files:**
- Modify: `skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py`
- Test: `tests/test_generate_excalidraw.py`

**Interfaces:**
- Consumes: `OutlineNode`, `ValidatedOutline` (Task 1).
- Produces:
  - `NODE_WIDTH = 220`, `NODE_HEIGHT = 70`, `SIBLING_GAP = 30`, `LEVEL_GAP = 260`, `RADIUS_STEP = 260`
  - `@dataclass class NodePosition: x: float; y: float; width: float = NODE_WIDTH; height: float = NODE_HEIGHT`
  - `def compute_tree_layout(outline: ValidatedOutline) -> dict[str, NodePosition]` (keys are every node's `id` plus the sentinel `"__root__"`)
  - `def compute_radial_layout(outline: ValidatedOutline) -> dict[str, NodePosition]` (same key shape)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_generate_excalidraw.py` (before the `if __name__ == "__main__":` line):

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_generate_excalidraw -v`
Expected: `AttributeError: module 'generate_excalidraw' has no attribute 'compute_tree_layout'`.

- [ ] **Step 3: Implement the layout functions**

Append to `skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py` (add `import math` to the top-of-file imports alongside the existing ones):

```python
NODE_WIDTH = 220
NODE_HEIGHT = 70
SIBLING_GAP = 30
LEVEL_GAP = 260
RADIUS_STEP = 260


@dataclass
class NodePosition:
    x: float
    y: float
    width: float = NODE_WIDTH
    height: float = NODE_HEIGHT


def compute_tree_layout(outline: ValidatedOutline) -> dict[str, NodePosition]:
    positions: dict[str, NodePosition] = {}
    next_row = [0.0]

    def place(node: OutlineNode) -> float:
        if not node.children:
            y = next_row[0]
            next_row[0] += NODE_HEIGHT + SIBLING_GAP
        else:
            child_ys = [place(child) for child in node.children]
            y = sum(child_ys) / len(child_ys)
        x = (node.depth - 1) * (NODE_WIDTH + LEVEL_GAP)
        positions[node.id] = NodePosition(x=x, y=y)
        return y

    root_ys = [place(node) for node in outline.nodes]
    root_y = sum(root_ys) / len(root_ys)
    positions["__root__"] = NodePosition(x=-(NODE_WIDTH + LEVEL_GAP), y=root_y)
    return positions


def _leaf_count(node: OutlineNode) -> int:
    if not node.children:
        return 1
    return sum(_leaf_count(child) for child in node.children)


def compute_radial_layout(outline: ValidatedOutline) -> dict[str, NodePosition]:
    positions: dict[str, NodePosition] = {"__root__": NodePosition(x=0.0, y=0.0)}
    total_leaves = sum(_leaf_count(node) for node in outline.nodes)
    two_pi = 2 * math.pi

    def place(node: OutlineNode, start_angle: float, span: float) -> None:
        angle = start_angle + span / 2
        radius = node.depth * RADIUS_STEP
        positions[node.id] = NodePosition(x=radius * math.cos(angle), y=radius * math.sin(angle))

        if node.children:
            child_total = sum(_leaf_count(child) for child in node.children)
            cursor = start_angle
            for child in node.children:
                child_span = span * (_leaf_count(child) / child_total)
                place(child, cursor, child_span)
                cursor += child_span

    cursor = 0.0
    for node in outline.nodes:
        node_span = two_pi * (_leaf_count(node) / total_leaves)
        place(node, cursor, node_span)
        cursor += node_span

    return positions
```

Note: the radial layout allocates a distinct angular sector per branch proportional to its leaf count and grows the radius strictly with depth; it does not attempt full pixel-level collision avoidance for very wide, shallow trees (a known, documented simplification — real overlap only shows up with dozens of same-depth siblings, well beyond the 5-level/short-label limits this skill enforces).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_generate_excalidraw -v`
Expected: `OK` (13 tests pass).

- [ ] **Step 5: Commit**

```bash
git add skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py tests/test_generate_excalidraw.py
git commit -m "feat: add radial and tree layout algorithms for the Excalidraw mindmap"
```

---

### Task 3: Excalidraw element and style builders

**Files:**
- Modify: `skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py`
- Test: `tests/test_generate_excalidraw.py`

**Interfaces:**
- Consumes: `NodePosition` (Task 2).
- Produces:
  - `DEPTH_COLORS: list[tuple[str, str]]`
  - `def build_rectangle(element_id: str, pos: NodePosition, *, depth: int, action: str) -> dict[str, Any]`
  - `def build_text(element_id: str, container_id: str, pos: NodePosition, text: str) -> dict[str, Any]`
  - `def build_arrow(element_id: str, start_id: str, end_id: str, start_pos: NodePosition, end_pos: NodePosition) -> dict[str, Any]`
  - `def build_obsidian_uri(vault_name: str, note_relative_path: str, anchor: str | None) -> str`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_generate_excalidraw.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_generate_excalidraw -v`
Expected: `AttributeError: module 'generate_excalidraw' has no attribute 'build_rectangle'`.

- [ ] **Step 3: Implement the builders**

Append to `skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py` (add `import urllib.parse` and `import zlib` to the top-of-file imports):

```python
DEPTH_COLORS = [
    ("#1e1e2e", "#ffffff"),
    ("#ffd8a8", "#e8590c"),
    ("#b2f2bb", "#2b8a3e"),
    ("#a5d8ff", "#1864ab"),
    ("#eebefa", "#862e9c"),
    ("#ffc9c9", "#c92a2a"),
]


def _color_for_depth(depth: int) -> tuple[str, str]:
    return DEPTH_COLORS[depth % len(DEPTH_COLORS)]


def _stable_seed(value: str) -> int:
    return zlib.crc32(value.encode("utf-8")) % 2_000_000_000 + 1


def _edge_point(pos: NodePosition, toward: NodePosition) -> tuple[float, float]:
    center_x, center_y = pos.x + pos.width / 2, pos.y + pos.height / 2
    toward_x, toward_y = toward.x + toward.width / 2, toward.y + toward.height / 2
    dx, dy = toward_x - center_x, toward_y - center_y
    if dx == 0 and dy == 0:
        return center_x, center_y
    scale_x = (pos.width / 2) / abs(dx) if dx else math.inf
    scale_y = (pos.height / 2) / abs(dy) if dy else math.inf
    scale = min(scale_x, scale_y)
    return center_x + dx * scale, center_y + dy * scale


def build_rectangle(element_id: str, pos: NodePosition, *, depth: int, action: str) -> dict[str, Any]:
    background, stroke = _color_for_depth(depth)
    stroke_style = "solid"
    if action == "link":
        stroke_style = "dashed"
    elif action == "manual":
        stroke_style = "dotted"
        background, stroke = "#f1f3f5", "#adb5bd"

    return {
        "type": "rectangle",
        "id": element_id,
        "x": pos.x,
        "y": pos.y,
        "width": pos.width,
        "height": pos.height,
        "angle": 0,
        "strokeColor": stroke,
        "backgroundColor": background,
        "fillStyle": "hachure",
        "strokeWidth": 2,
        "strokeStyle": stroke_style,
        "roughness": 2,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": {"type": 3},
        "seed": _stable_seed(element_id),
        "version": 1,
        "versionNonce": _stable_seed(element_id + "-nonce"),
        "isDeleted": False,
        "boundElements": [{"id": f"{element_id}-text", "type": "text"}],
        "updated": 1,
        "link": None,
        "locked": False,
    }


def build_text(element_id: str, container_id: str, pos: NodePosition, text: str) -> dict[str, Any]:
    return {
        "type": "text",
        "id": element_id,
        "x": pos.x + 8,
        "y": pos.y + pos.height / 2 - 10,
        "width": pos.width - 16,
        "height": 20,
        "angle": 0,
        "strokeColor": "#1e1e2e",
        "backgroundColor": "transparent",
        "fillStyle": "hachure",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 2,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": None,
        "seed": _stable_seed(element_id),
        "version": 1,
        "versionNonce": _stable_seed(element_id + "-nonce"),
        "isDeleted": False,
        "updated": 1,
        "link": None,
        "locked": False,
        "text": text,
        "fontSize": 16,
        "fontFamily": 1,
        "textAlign": "center",
        "verticalAlign": "middle",
        "containerId": container_id,
        "originalText": text,
        "lineHeight": 1.25,
    }


def build_arrow(
    element_id: str, start_id: str, end_id: str, start_pos: NodePosition, end_pos: NodePosition
) -> dict[str, Any]:
    start_x, start_y = _edge_point(start_pos, end_pos)
    end_x, end_y = _edge_point(end_pos, start_pos)

    return {
        "type": "arrow",
        "id": element_id,
        "x": start_x,
        "y": start_y,
        "width": end_x - start_x,
        "height": end_y - start_y,
        "angle": 0,
        "strokeColor": "#495057",
        "backgroundColor": "transparent",
        "fillStyle": "hachure",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 2,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": {"type": 2},
        "seed": _stable_seed(element_id),
        "version": 1,
        "versionNonce": _stable_seed(element_id + "-nonce"),
        "isDeleted": False,
        "boundElements": [],
        "updated": 1,
        "link": None,
        "locked": False,
        "points": [[0, 0], [end_x - start_x, end_y - start_y]],
        "lastCommittedPoint": None,
        "startBinding": {"elementId": start_id, "focus": 0, "gap": 4},
        "endBinding": {"elementId": end_id, "focus": 0, "gap": 4},
        "startArrowhead": None,
        "endArrowhead": "triangle",
    }


def build_obsidian_uri(vault_name: str, note_relative_path: str, anchor: str | None) -> str:
    file_value = note_relative_path
    if file_value.endswith(".md"):
        file_value = file_value[: -len(".md")]
    if anchor:
        file_value = f"{file_value}#{anchor}"
    query = urllib.parse.urlencode({"vault": vault_name, "file": file_value})
    return f"obsidian://open?{query}"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_generate_excalidraw -v`
Expected: `OK` (21 tests pass).

- [ ] **Step 5: Commit**

```bash
git add skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py tests/test_generate_excalidraw.py
git commit -m "feat: build styled Excalidraw rectangle, text, and arrow elements"
```

---

### Task 4: Document assembly

**Files:**
- Modify: `skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py`
- Test: `tests/test_generate_excalidraw.py`

**Interfaces:**
- Consumes: `ValidatedOutline`, `OutlineNode`, `NodePosition`, `build_rectangle`, `build_text`, `build_arrow`, `build_obsidian_uri` (Tasks 1–3).
- Produces: `EXCALIDRAW_TYPE`, `EXCALIDRAW_VERSION`, `EXCALIDRAW_SOURCE`, `def build_excalidraw_document(outline: ValidatedOutline, positions: dict[str, NodePosition], *, vault_name: str) -> dict[str, Any]`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_generate_excalidraw.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_generate_excalidraw -v`
Expected: `AttributeError: module 'generate_excalidraw' has no attribute 'build_excalidraw_document'`.

- [ ] **Step 3: Implement document assembly**

Append to `skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py`:

```python
EXCALIDRAW_TYPE = "excalidraw"
EXCALIDRAW_VERSION = 2
EXCALIDRAW_SOURCE = "https://github.com/khanh-an-569/web-to-obsidian"


def build_excalidraw_document(
    outline: ValidatedOutline, positions: dict[str, NodePosition], *, vault_name: str
) -> dict[str, Any]:
    elements: list[dict[str, Any]] = []

    root_pos = positions["__root__"]
    elements.append(build_rectangle("root", root_pos, depth=0, action="full"))
    elements.append(build_text("root-text", "root", root_pos, outline.title))

    def walk(node: OutlineNode, parent_id: str, parent_pos: NodePosition) -> None:
        pos = positions[node.id]
        elements.append(build_rectangle(node.id, pos, depth=node.depth, action=node.action))
        elements.append(build_text(f"{node.id}-text", node.id, pos, node.text))
        if node.action in ("condensed", "link"):
            elements[-2]["link"] = build_obsidian_uri(
                vault_name, outline.source_note_path, node.source_anchor
            )
        elements.append(build_arrow(f"{parent_id}->{node.id}", parent_id, node.id, parent_pos, pos))
        for child in node.children:
            walk(child, node.id, pos)

    for node in outline.nodes:
        walk(node, "root", root_pos)

    return {
        "type": EXCALIDRAW_TYPE,
        "version": EXCALIDRAW_VERSION,
        "source": EXCALIDRAW_SOURCE,
        "elements": elements,
        "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
        "files": {},
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_generate_excalidraw -v`
Expected: `OK` (24 tests pass).

- [ ] **Step 5: Commit**

```bash
git add skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py tests/test_generate_excalidraw.py
git commit -m "feat: assemble the full .excalidraw document from an outline and layout"
```

---

### Task 5: Publish — atomic write and idempotent note link-back

**Files:**
- Modify: `skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py`
- Test: `tests/test_generate_excalidraw.py`

**Interfaces:**
- Consumes: nothing new (pure file I/O).
- Produces:
  - `def write_excalidraw_file(document: dict[str, Any], target_path: Path, *, regenerate: bool) -> str` (returns `"created"` or `"regenerated"`; raises `MindmapError` if the file exists and `regenerate` is `False`)
  - `EXCALIDRAW_SECTION_HEADING = "## Sơ đồ Excalidraw"`
  - `def append_diagram_link(note_path: Path, diagram_filename: str) -> bool` (returns `True` if it modified the note, `False` if the link already existed)
  - `def _atomic_replace_text(path: Path, text: str) -> None`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_generate_excalidraw.py` (add `import tempfile` and `from pathlib import Path` are already imported at the top; no new top-of-test-file imports needed beyond what's already there):

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_generate_excalidraw -v`
Expected: `AttributeError: module 'generate_excalidraw' has no attribute 'write_excalidraw_file'`.

- [ ] **Step 3: Implement the publish functions**

Append to `skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py` (add `import json`, `import os`, `import tempfile`, and `from pathlib import Path` to the top-of-file imports):

```python
def write_excalidraw_file(document: dict[str, Any], target_path: Path, *, regenerate: bool) -> str:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, ensure_ascii=False, indent=2)

    if target_path.exists() and not regenerate:
        raise MindmapError(f"{target_path} already exists. Pass --regenerate to overwrite it.")

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=target_path.parent,
            prefix=f".{target_path.stem}-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)

        if target_path.exists():
            os.replace(temp_path, target_path)
            temp_path = None
            return "regenerated"

        try:
            os.link(temp_path, target_path)
        except FileExistsError as exc:
            raise MindmapError(
                f"{target_path} already exists. Pass --regenerate to overwrite it."
            ) from exc
        return "created"
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def _atomic_replace_text(path: Path, text: str) -> None:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.stem}-append-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


EXCALIDRAW_SECTION_HEADING = "## Sơ đồ Excalidraw"


def append_diagram_link(note_path: Path, diagram_filename: str) -> bool:
    text = note_path.read_text(encoding="utf-8")
    embed = f"![[{diagram_filename}]]"
    if embed in text:
        return False

    separator = "" if text.endswith("\n") else "\n"
    if EXCALIDRAW_SECTION_HEADING in text:
        addition = f"\n{embed}\n"
    else:
        addition = f"{separator}\n{EXCALIDRAW_SECTION_HEADING}\n{embed}\n"

    _atomic_replace_text(note_path, text + addition)
    return True
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_generate_excalidraw -v`
Expected: `OK` (30 tests pass).

- [ ] **Step 5: Commit**

```bash
git add skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py tests/test_generate_excalidraw.py
git commit -m "feat: publish .excalidraw files atomically and link them back into the note"
```

---

### Task 6: CLI wiring

**Files:**
- Modify: `skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py`
- Test: `tests/test_generate_excalidraw.py`

**Interfaces:**
- Consumes: `validate_outline`, `compute_tree_layout`, `compute_radial_layout`, `build_excalidraw_document`, `write_excalidraw_file`, `append_diagram_link` (Tasks 1–5).
- Produces:
  - `def resolve_vault(vault_argument: str | None) -> Path`
  - `def _config_value(config_path: Path, key: str) -> str | None`
  - `def build_parser() -> argparse.ArgumentParser`
  - `def run(args: argparse.Namespace) -> dict[str, Any]`
  - `def main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write the failing tests**

Add `import json` to the top-of-file imports in `tests/test_generate_excalidraw.py` (alongside `import importlib.util`), then append below the existing test classes:

```python
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
            config_path = root / "web-to-obsidian.yaml"
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

            expected_path = vault / "20 Knowledge" / "Excalidraw" / "test-note.excalidraw"
            self.assertEqual(Path(result["path"]), expected_path)
            self.assertTrue(expected_path.exists())

    def test_run_ignores_config_file_when_output_dir_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vault, _note_path = self.make_vault_with_note(root)
            outline_path = self.make_outline_file(root, "10 Sources/test-note.md")
            config_path = root / "web-to-obsidian.yaml"
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
            self.assertEqual(Path(result["path"]), vault / "explicit-dir" / "test-note.excalidraw")


if __name__ == "__main__":
    unittest.main()
```

Move the pre-existing `if __name__ == "__main__": unittest.main()` block (currently at the end of the file from Task 1) so it appears only once, after this new class.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_generate_excalidraw -v`
Expected: `AttributeError: module 'generate_excalidraw' has no attribute 'resolve_vault'`.

- [ ] **Step 3: Implement the CLI**

Append to `skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py` (add `import argparse`, `import re`, and `import sys` to the top-of-file imports):

```python
def resolve_vault(vault_argument: str | None) -> Path:
    candidate = (
        vault_argument
        or os.environ.get("WEB_TO_OBSIDIAN_VAULT_PATH")
        or os.environ.get("OBSIDIAN_VAULT_PATH")
    )
    if not candidate:
        raise MindmapError(
            "Could not resolve the Obsidian vault. Pass --vault, or set "
            "WEB_TO_OBSIDIAN_VAULT_PATH / OBSIDIAN_VAULT_PATH."
        )
    vault = Path(candidate).expanduser().resolve()
    if not vault.is_dir():
        raise MindmapError(f"Vault directory does not exist: {vault}")
    return vault


def _config_value(config_path: Path, key: str) -> str | None:
    if not config_path.is_file():
        return None
    pattern = re.compile(rf'^\s*{re.escape(key)}\s*:\s*"?([^"\n]+?)"?\s*$', re.MULTILINE)
    match = pattern.search(config_path.read_text(encoding="utf-8"))
    return match.group(1).strip() if match else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a brainstorm-style Excalidraw diagram from an outline JSON file."
    )
    parser.add_argument("--outline-file", required=True, help="Path to the outline JSON file.")
    parser.add_argument(
        "--vault",
        help="Obsidian vault root. Defaults to WEB_TO_OBSIDIAN_VAULT_PATH or OBSIDIAN_VAULT_PATH.",
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "Directory (relative to the vault) for the .excalidraw file. Defaults to "
            "'excalidraw_output_dir' from --config-file, or the source note's folder."
        ),
    )
    parser.add_argument(
        "--config-file",
        help=(
            "Path to web-to-obsidian.yaml to read an 'excalidraw_output_dir' default from. "
            "Optional; no config file is read when omitted."
        ),
    )
    parser.add_argument(
        "--export-dir",
        help="Additional standalone directory to also write a copy of the .excalidraw file.",
    )
    parser.add_argument(
        "--regenerate", action="store_true", help="Overwrite an existing .excalidraw file for this note."
    )
    parser.add_argument(
        "--no-link-back",
        action="store_true",
        help="Skip appending the diagram embed link to the source note.",
    )
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    outline_data = json.loads(Path(args.outline_file).read_text(encoding="utf-8"))
    outline = validate_outline(outline_data)

    vault = resolve_vault(args.vault)
    note_path = (vault / outline.source_note_path).resolve()
    note_path.relative_to(vault)
    if not note_path.is_file():
        raise MindmapError(f"Source note does not exist: {note_path}")

    positions = (
        compute_radial_layout(outline) if outline.layout == "radial" else compute_tree_layout(outline)
    )
    document = build_excalidraw_document(outline, positions, vault_name=vault.name)

    output_dir_value = args.output_dir
    if not output_dir_value and args.config_file:
        output_dir_value = _config_value(Path(args.config_file), "excalidraw_output_dir")
    output_dir = (vault / output_dir_value) if output_dir_value else note_path.parent
    diagram_filename = f"{note_path.stem}.excalidraw"
    target_path = output_dir / diagram_filename

    status = write_excalidraw_file(document, target_path, regenerate=args.regenerate)

    linked = False
    if not args.no_link_back:
        linked = append_diagram_link(note_path, diagram_filename)

    exported_to = None
    if args.export_dir:
        export_path = Path(args.export_dir).expanduser().resolve() / diagram_filename
        write_excalidraw_file(document, export_path, regenerate=True)
        exported_to = str(export_path)

    return {
        "status": status,
        "path": str(target_path),
        "linked_from_note": linked,
        "exported_to": exported_to,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run(args)
    except (MindmapError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_generate_excalidraw -v`
Expected: `OK` (35 tests pass).

- [ ] **Step 5: Run the whole new test module once more with the discovery runner, and commit**

Run: `python -m unittest discover -s tests -q`
Expected: `OK` (all suites, including this new one, pass).

```bash
git add skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py tests/test_generate_excalidraw.py
git commit -m "feat: wire the Excalidraw mindmap CLI end to end"
```

---

### Task 7: New skill documentation (SKILL.md, outline schema reference, Codex metadata)

**Files:**
- Create: `skills/obsidian-excalidraw-mindmap/SKILL.md`
- Create: `skills/obsidian-excalidraw-mindmap/references/outline-schema.md`
- Create: `skills/obsidian-excalidraw-mindmap/agents/openai.yaml`

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: the skill's public contract, required by Task 10's `tests/test_repository.py` assertions (`SKILL.md` frontmatter `name`/`description`, `agents/openai.yaml` containing `$obsidian-excalidraw-mindmap` in `interface.default_prompt`).

- [ ] **Step 1: Create `skills/obsidian-excalidraw-mindmap/agents/openai.yaml`**

```yaml
interface:
  display_name: "Obsidian Excalidraw Mindmap"
  short_description: "Turn a captured note into an Excalidraw diagram"
  default_prompt: "Use $obsidian-excalidraw-mindmap to turn my captured note into a brainstorm-style Excalidraw diagram."

policy:
  allow_implicit_invocation: true
```

- [ ] **Step 2: Create `skills/obsidian-excalidraw-mindmap/references/outline-schema.md`**

```markdown
# Outline JSON schema

This is the exact contract `scripts/generate_excalidraw.py` expects. Build it
strictly from the source note's existing heading/bullet structure — never
invent ideas the note does not contain.

```json
{
  "title": "Note title",
  "source_note_path": "relative/path/to/note.md",
  "layout": "radial",
  "long_content_strategy": "condense",
  "nodes": [
    {
      "id": "n1",
      "text": "Main idea 1",
      "action": "full",
      "source_anchor": null,
      "children": []
    }
  ]
}
```

- `layout`: `"radial"` (center topic, branches radiate outward) or `"tree"`
  (single-direction hierarchical layout). Ask the user; do not choose silently.
- `long_content_strategy`: chosen once per run, applied consistently to every
  node that needs more than its `action: "full"` character budget:
  - `"link"` — keep a short topic label; the script attaches an `obsidian://`
    link back to `source_note_path#source_anchor`.
  - `"condense"` — split the long block into more, smaller **child** nodes
    (further branching), recursively, instead of one lossy summary line.
  - `"manual"` — a short placeholder the user is expected to fill in later
    directly in Excalidraw.
- `action` per node: `"full"`, `"condensed"`, `"link"`, or `"manual"`.
  `source_anchor` is required whenever `action != "full"`.
- `children` nests arbitrarily — this is what allows splitting a long idea
  into more nodes instead of losing it in a single summary.
- Limits enforced by the script (it will reject the outline, never silently
  truncate): text length per action — `full` ≤ 80 chars, `condensed` ≤ 60,
  `link` ≤ 40, `manual` ≤ 40 — and a maximum depth of 5, where a top-level
  node (a direct entry of `nodes`) is depth 1. If a branch would need to go
  deeper than 5 levels and is still too long, use `"link"` for that node
  instead of forcing it through.
```

- [ ] **Step 3: Create `skills/obsidian-excalidraw-mindmap/SKILL.md`**

```markdown
---
name: obsidian-excalidraw-mindmap
description: Use when a user asks to turn a captured Obsidian source note into a brainstorm-style Excalidraw mind map or diagram; dùng khi người dùng muốn biến một note nguồn đã capture trong Obsidian thành sơ đồ tư duy/brainstorm dạng Excalidraw.
---

# Obsidian Excalidraw Mindmap

Turn one already-captured source note into a polished, branching Excalidraw diagram without inventing or reinterpreting its ideas. / Biến một source note đã capture sẵn thành sơ đồ Excalidraw rẽ nhánh, đẹp mắt, không bịa hay diễn giải lại ý gốc.

## When to use / Khi nào dùng

Use on a note already created by `web-to-obsidian`, either right after capture (offered as an optional follow-up) or later against any existing captured note the user names explicitly. Never guess which note to use. / Dùng trên note đã được `web-to-obsidian` tạo ra, ngay sau khi capture hoặc sau này với note đã có tên rõ ràng. Không tự đoán note.

## Workflow / Quy trình

1. Ask the user two choices before building anything: `layout` (`radial` mindmap or left-to-right `tree`) and `long_content_strategy` (`link` back to the note, `condense` by splitting long paragraphs into further child nodes, or `manual` placeholders). Apply one strategy consistently for the whole diagram; never mix strategies within a single run. / Hỏi layout và cách xử lý đoạn dài trước, áp dụng nhất quán cho cả sơ đồ.
2. Read the source note and build an outline strictly from its existing heading/bullet structure — never invent ideas that are not in the note. Follow [references/outline-schema.md](references/outline-schema.md) exactly. / Đọc note, dựng outline đúng cấu trúc có sẵn, không bịa ý.
3. Write the outline to a JSON file and run `scripts/generate_excalidraw.py`. The script never reads note content itself and makes no content judgments — it only lays out, styles, and publishes exactly the outline it is given. Pass `--config-file` pointing at the vault's `web-to-obsidian.yaml` only when the user wants diagrams placed under its `excalidraw_output_dir` instead of next to the source note; otherwise omit it.
4. Report the script's JSON result (`status`, `path`, `linked_from_note`, `exported_to`) to the user, including the full path to the generated `.excalidraw` file.

From repository root / Từ repo root:

```powershell
python .\skills\obsidian-excalidraw-mindmap\scripts\generate_excalidraw.py `
  --outline-file "$env:TEMP\outline.json" `
  --vault "D:\Notes\Second Brain"
```

To also keep a portable copy outside the vault / Để giữ thêm bản standalone ngoài vault:

```powershell
python .\skills\obsidian-excalidraw-mindmap\scripts\generate_excalidraw.py `
  --outline-file "$env:TEMP\outline.json" `
  --vault "D:\Notes\Second Brain" `
  --export-dir "D:\Exports\Diagrams"
```

To overwrite a diagram already generated for that note, add `--regenerate`; only do this after re-verifying the outline against the current note content. / Để ghi đè sơ đồ đã có, thêm `--regenerate`; chỉ dùng khi outline đã được xác minh lại.

For an installed skill, resolve the directory containing this loaded `SKILL.md`, then run its `scripts/generate_excalidraw.py`; do not assume the repository layout.

## Quick Reference

| Situation / Tình huống | Action / Hành động |
|---|---|
| Note has clear headings/bullets | Use them as-is with action `full` |
| A bullet is a long paragraph | Split it into child nodes under `condense`, or use `link` |
| User hasn't picked layout/strategy yet | Ask before building the outline |
| Diagram already exists for this note | Do not overwrite without `--regenerate` |
| Vault not resolvable | Ask for `--vault`; never guess a personal path |

## Common Mistakes / Lỗi thường gặp

- Inventing ideas, summaries, or structure that is not already in the note.
- Mixing `link`/`condense`/`manual` strategies within the same diagram.
- Guessing the vault path or the note to diagram instead of resolving it explicitly.
- Overwriting an existing `.excalidraw` file without `--regenerate`.
- Touching the note's frontmatter or its `Ghi chú của tôi` section — the skill only appends a diagram embed link.

Report the helper's status (`created`, `regenerated`, or `error`) plus the final `.excalidraw` path. / Báo trạng thái và đường dẫn file cuối cùng.
```

- [ ] **Step 4: Verify the new files parse and the CLI help works**

Run: `python .\skills\obsidian-excalidraw-mindmap\scripts\generate_excalidraw.py --help`
Expected: argparse help text listing `--outline-file`, `--vault`, `--output-dir`, `--export-dir`, `--regenerate`, `--no-link-back`.

- [ ] **Step 5: Commit**

```bash
git add skills/obsidian-excalidraw-mindmap/SKILL.md skills/obsidian-excalidraw-mindmap/references/outline-schema.md skills/obsidian-excalidraw-mindmap/agents/openai.yaml
git commit -m "docs: add SKILL.md, outline schema reference, and Codex metadata for the mindmap skill"
```

---

### Task 8: Optional follow-up hook in `web-to-obsidian`

**Files:**
- Modify: `skills/web-to-obsidian/SKILL.md`

**Interfaces:**
- Consumes: nothing (documentation only); references the `obsidian-excalidraw-mindmap` skill created in Task 7 by name.
- Produces: an additive step 8 in the existing numbered workflow.

- [ ] **Step 1: Add the optional follow-up step**

In `skills/web-to-obsidian/SKILL.md`, the numbered `## Workflow / Quy trình` list currently ends at item 7 (`... preserves the existing 'Ghi chú của tôi' section and custom frontmatter. Rich HTML capture deliberately omits a visible 'Nội dung nguồn' wrapper heading so the source hierarchy starts cleanly below the note H1. / Mặc định không sửa note trùng; chỉ refresh khi người dùng yêu cầu rõ ràng.`). Add a new item 8 immediately after it, before the `From repository root / Từ repo root:` line:

```markdown
8. After a `created`, `duplicate`, or `refreshed` result, optionally offer to turn the note into a brainstorm-style Excalidraw diagram: ask whether the user wants one, and if so which `layout` (`radial`/`tree`) and `long_content_strategy` (`link`/`condense`/`manual`), then invoke the `obsidian-excalidraw-mindmap` skill with the note's resolved path. This step is always optional and never automatic, and it never alters the capture result recorded above. / Sau khi capture xong, có thể tuỳ chọn hỏi tạo sơ đồ Excalidraw kiểu brainstorm; nếu đồng ý thì gọi skill `obsidian-excalidraw-mindmap` với đường dẫn note. Bước này luôn là tuỳ chọn, không tự động, không ảnh hưởng kết quả capture.
```

- [ ] **Step 2: Verify no other workflow step numbering broke**

Run: `python -c "import re,sys; text=open('skills/web-to-obsidian/SKILL.md', encoding='utf-8').read(); nums=[int(n) for n in re.findall(r'^(\d+)\.', text, re.MULTILINE)]; sys.exit(0 if nums == list(range(1, len(nums)+1)) else 1)"`
Expected: exit code `0` (no output means the numbered list is exactly `1..8` in order).

- [ ] **Step 3: Commit**

```bash
git add skills/web-to-obsidian/SKILL.md
git commit -m "docs: offer the Excalidraw mindmap skill as an optional post-capture step"
```

---

### Task 9: Manifests and config examples

**Files:**
- Modify: `plugin.json`
- Modify: `.codex-plugin/plugin.json`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `web-to-obsidian.example.yaml`

**Interfaces:**
- Consumes: nothing (config only).
- Produces: manifest state consumed by Task 10's updated `tests/test_repository.py`.

- [ ] **Step 1: Update `plugin.json` (root)**

Replace its contents with (note the version bump `0.4.0` → `0.5.0`, the two new keywords, the updated `longDescription`, and the added `"Diagram export"` capability — `defaultPrompt` is deliberately left unchanged to respect its existing ≤3-item cap without arbitrarily dropping an existing prompt):

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "web-to-obsidian",
  "version": "0.5.0",
  "description": "Capture browser sources into a local Obsidian vault, configure safe formatting for the resulting web clips, and turn a captured note into a brainstorm-style Excalidraw diagram.",
  "author": {
    "name": "khanh-an-569"
  },
  "homepage": "https://github.com/khanh-an-569/web-to-obsidian#readme",
  "repository": "https://github.com/khanh-an-569/web-to-obsidian",
  "license": "MIT",
  "keywords": [
    "obsidian",
    "browser-extension",
    "web-capture",
    "tavily",
    "markdown",
    "excalidraw",
    "mindmap"
  ],
  "skills": "./skills/",
  "interface": {
    "displayName": "Web to Obsidian",
    "shortDescription": "Capture and format web sources in Obsidian.",
    "longDescription": "Three focused workflows: saving a browser tab, selection, or public URL into a local Obsidian vault; configuring safe Markdown formatting, scoped CSS, and export preparation for captured web notes; and turning a captured note into a brainstorm-style Excalidraw diagram.",
    "developerName": "khanh-an-569",
    "category": "Productivity",
    "capabilities": [
      "Browser context",
      "Local vault write",
      "Public web extraction",
      "Vault formatting setup",
      "Diagram export"
    ],
    "defaultPrompt": [
      "Save the current browser tab to my Obsidian vault.",
      "Save my selected text and preserve its source URL.",
      "Set up safe formatting for web clips in my Obsidian vault."
    ],
    "brandColor": "#7C3AED"
  }
}
```

- [ ] **Step 2: Mirror the exact same content into `.codex-plugin/plugin.json`, minus `$schema`**

Replace its contents with:

```json
{
  "name": "web-to-obsidian",
  "version": "0.5.0",
  "description": "Capture browser sources into a local Obsidian vault, configure safe formatting for the resulting web clips, and turn a captured note into a brainstorm-style Excalidraw diagram.",
  "author": {
    "name": "khanh-an-569"
  },
  "homepage": "https://github.com/khanh-an-569/web-to-obsidian#readme",
  "repository": "https://github.com/khanh-an-569/web-to-obsidian",
  "license": "MIT",
  "keywords": [
    "obsidian",
    "browser-extension",
    "web-capture",
    "tavily",
    "markdown",
    "excalidraw",
    "mindmap"
  ],
  "skills": "./skills/",
  "interface": {
    "displayName": "Web to Obsidian",
    "shortDescription": "Capture and format web sources in Obsidian.",
    "longDescription": "Three focused workflows: saving a browser tab, selection, or public URL into a local Obsidian vault; configuring safe Markdown formatting, scoped CSS, and export preparation for captured web notes; and turning a captured note into a brainstorm-style Excalidraw diagram.",
    "developerName": "khanh-an-569",
    "category": "Productivity",
    "capabilities": [
      "Browser context",
      "Local vault write",
      "Public web extraction",
      "Vault formatting setup",
      "Diagram export"
    ],
    "defaultPrompt": [
      "Save the current browser tab to my Obsidian vault.",
      "Save my selected text and preserve its source URL.",
      "Set up safe formatting for web clips in my Obsidian vault."
    ],
    "brandColor": "#7C3AED"
  }
}
```

- [ ] **Step 3: Update `.claude-plugin/plugin.json`**

Replace its contents with:

```json
{
  "name": "web-to-obsidian",
  "description": "Capture browser sources into a local Obsidian vault, configure safe formatting for the resulting web clips, and turn a captured note into a brainstorm-style Excalidraw diagram.",
  "version": "0.5.0",
  "author": { "name": "khanh-an-569" },
  "homepage": "https://github.com/khanh-an-569/web-to-obsidian#readme",
  "repository": "https://github.com/khanh-an-569/web-to-obsidian",
  "license": "MIT",
  "keywords": ["obsidian", "browser-extension", "web-capture", "tavily", "markdown", "excalidraw", "mindmap"]
}
```

- [ ] **Step 4: Update `.claude-plugin/marketplace.json`**

Replace its contents with:

```json
{
  "name": "web-to-obsidian",
  "description": "Personal marketplace for the web-to-obsidian Claude Code plugin.",
  "owner": { "name": "khanh-an-569" },
  "plugins": [
    {
      "name": "web-to-obsidian",
      "source": "./",
      "description": "Capture web sources into Obsidian, format the resulting clips, and turn notes into brainstorm-style Excalidraw diagrams."
    }
  ]
}
```

- [ ] **Step 5: Add the optional `excalidraw_output_dir` example key**

In `web-to-obsidian.example.yaml`, insert immediately after the `vault_root:` line and its trailing blank line (before the `folders:` block):

```yaml
# Optional: where generated Excalidraw diagrams are written, relative to vault_root.
# Defaults to the same folder as the source note when unset.
excalidraw_output_dir: "20 Knowledge/Excalidraw"

```

- [ ] **Step 6: Verify JSON files still parse and the portable/codex manifests still match apart from `$schema`**

Run: `python -c "import json; a=json.load(open('plugin.json', encoding='utf-8')); b=json.load(open('.codex-plugin/plugin.json', encoding='utf-8')); a.pop('$schema'); assert a == b, 'manifests diverge'; print('OK')"`
Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add plugin.json .codex-plugin/plugin.json .claude-plugin/plugin.json .claude-plugin/marketplace.json web-to-obsidian.example.yaml
git commit -m "chore: list the Excalidraw mindmap skill across all plugin manifests"
```

---

### Task 10: Architecture docs and repository tests

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/architecture.vi.md`
- Modify: `tests/test_repository.py`

**Interfaces:**
- Consumes: the skill inventory and manifest state from Tasks 7 and 9.
- Produces: updated repository-wide consistency checks covering the third skill.

- [ ] **Step 1: Write the failing test changes first**

In `tests/test_repository.py`, update `expected_skill_names` inside `test_manifest_and_skill_metadata`:

```python
        expected_skill_names = (
            "web-to-obsidian",
            "obsidian-clip-beautifier",
            "obsidian-excalidraw-mindmap",
        )
```

And update the exact-set assertion in `test_plugin_interface_matches_the_installed_user_experience`:

```python
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
```

- [ ] **Step 2: Run the repository test to verify it fails**

Run: `python -m unittest tests.test_repository -v`
Expected: `FAIL` — `test_architecture_docs_list_every_skill` fails because `docs/architecture.md`/`docs/architecture.vi.md` don't yet have a `### \`obsidian-excalidraw-mindmap\`` heading.

- [ ] **Step 3: Add the architecture section (English)**

In `docs/architecture.md`, insert a new subsection immediately after the existing `### \`obsidian-clip-beautifier\`` section's two paragraphs and before `### Properties, Bases, and MOCs`:

```markdown
### `obsidian-excalidraw-mindmap`

Turns one already-captured note into a brainstorm-style Excalidraw diagram: Claude builds a strictly source-derived outline (never inventing ideas), and `generate_excalidraw.py` computes a deterministic radial or tree layout, colors nodes by branch depth, applies Excalidraw's native hand-drawn styling, and publishes the result atomically, no-clobber, both inside the vault (linked from the source note) and optionally as a standalone file. It never captures browser content and never makes content judgments itself — content fidelity stays with the outline Claude provides, and layout/style/publication stay deterministic and testable in the script.

The skill is offered as an optional follow-up right after `web-to-obsidian` finishes a capture, or invoked manually against any already-captured note the user names explicitly. It never guesses which note to diagram.
```

- [ ] **Step 4: Add the architecture section (Vietnamese)**

In `docs/architecture.vi.md`, insert the matching subsection immediately after the existing `### \`obsidian-clip-beautifier\`` section's two paragraphs and before `### Properties, Bases và MOC`:

```markdown
### `obsidian-excalidraw-mindmap`

Biến một note đã capture sẵn thành sơ đồ Excalidraw kiểu brainstorm: Claude dựng outline bám chặt nguồn (không bịa ý), còn `generate_excalidraw.py` tính bố cục radial hoặc cây tất định, tô màu node theo cấp nhánh, áp style vẽ tay gốc của Excalidraw, rồi publish nguyên tử, no-clobber, cả trong vault (link từ note gốc) lẫn bản standalone tuỳ chọn. Skill không tự lấy nội dung trình duyệt và không tự đưa ra phán đoán nội dung — độ trung thực nội dung nằm ở outline do Claude cung cấp, còn bố cục/style/publish luôn tất định và test được trong script.

Skill được gợi ý như một bước tuỳ chọn ngay sau khi `web-to-obsidian` capture xong, hoặc gọi thủ công trên bất kỳ note đã capture nào người dùng nêu rõ. Skill không bao giờ tự đoán note.
```

- [ ] **Step 5: Run the repository test again to verify it passes**

Run: `python -m unittest tests.test_repository -v`
Expected: `OK` (all `RepositoryTests` pass).

- [ ] **Step 6: Commit**

```bash
git add docs/architecture.md docs/architecture.vi.md tests/test_repository.py
git commit -m "test: extend repository consistency checks to the Excalidraw mindmap skill"
```

---

### Task 11: Full verification

**Files:** none (verification only).

**Interfaces:** none.

- [ ] **Step 1: Run the complete test suite**

Run: `python -m unittest discover -s tests -q`
Expected: `OK` — every suite passes, including `test_generate_excalidraw`, `test_repository`, and all pre-existing suites (`test_save_capture`, `test_audit_sensitive_urls`, `test_obsidian_clip_beautifier`, `test_check_no_secrets`, `test_findings_regressions`).

- [ ] **Step 2: Run the secret scanner**

Run: `python scripts/check_no_secrets.py --root .`
Expected: no findings printed, exit code `0`.

- [ ] **Step 3: Byte-compile every skill, script, and test module**

Run: `python -m compileall -q skills scripts tests`
Expected: no output, exit code `0`.

- [ ] **Step 4: Check for whitespace/EOF issues in the diff**

Run: `git diff --check`
Expected: no output.

- [ ] **Step 5: Validate the Claude Code plugin manifest, if the CLI is available**

Run: `claude plugin validate . --strict`
Expected: validation passes. If the `claude` CLI is not available in this environment, note that explicitly instead of skipping silently.

- [ ] **Step 6: Manual smoke test — generate one real diagram end to end**

Using a disposable test vault (not the user's real vault), create a small note, hand-write a matching outline JSON by hand (following `references/outline-schema.md`), run `generate_excalidraw.py` against it, and open the resulting `.excalidraw` file in a browser at excalidraw.com (drag-and-drop import) to visually confirm: nodes are colored by depth, hand-drawn style renders, arrows connect parent to child, and `link`-action nodes are clickable. Report which of these were verified and which could not be exercised in this environment (e.g., no internet access to excalidraw.com, or no Obsidian install to confirm the `obsidian://` URI opens correctly) — do not claim visual verification that was not actually performed.

- [ ] **Step 7: Report**

Summarize to the user: which runtime surfaces were tested (Claude Code script execution and `unittest` suite — confirmed; Codex `$obsidian-excalidraw-mindmap` invocation and the `obsidian://` URI opening in a real Obsidian install — not exercised in this environment, per Task 11 Step 6) and the final state of all 11 tasks.
