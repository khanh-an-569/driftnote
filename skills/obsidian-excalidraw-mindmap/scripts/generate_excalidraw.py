#!/usr/bin/env python3
"""Turn a strictly source-derived outline into a brainstorm-style Excalidraw diagram."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
import urllib.parse
import zlib
from dataclasses import dataclass, field
from pathlib import Path
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
        if node_id.endswith("-text"):
            raise MindmapError(
                f"Node id {node_id!r} is not allowed to end in '-text'; it would collide "
                "with that node's auto-generated text element id."
            )
        if node_id == "root":
            raise MindmapError(
                f"Node id {node_id!r} is not allowed; it collides with the reserved root node id."
            )
        if "->" in node_id:
            raise MindmapError(
                f"Node id {node_id!r} is not allowed to contain '->'; it would collide "
                "with the arrow-id naming convention."
            )
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
    positions: dict[str, NodePosition] = {
        "__root__": NodePosition(x=0.0 - NODE_WIDTH / 2, y=0.0 - NODE_HEIGHT / 2)
    }
    total_leaves = sum(_leaf_count(node) for node in outline.nodes)
    two_pi = 2 * math.pi

    # Guarantee that a full ring of `total_leaves` boxes placed side by side at any
    # depth's radius has enough circumference to avoid overlapping bounding boxes.
    min_ring_circumference = (NODE_WIDTH + SIBLING_GAP) * total_leaves
    min_radius_for_leaves = min_ring_circumference / two_pi
    effective_radius_step = max(RADIUS_STEP, min_radius_for_leaves)

    def place(node: OutlineNode, start_angle: float, span: float) -> None:
        angle = start_angle + span / 2
        radius = node.depth * effective_radius_step
        positions[node.id] = NodePosition(
            x=radius * math.cos(angle) - NODE_WIDTH / 2,
            y=radius * math.sin(angle) - NODE_HEIGHT / 2,
        )

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


DEPTH_COLORS = [
    ("#dbe4ff", "#364fc7"),
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
    query = urllib.parse.urlencode(
        {"vault": vault_name, "file": file_value}, quote_via=urllib.parse.quote
    )
    return f"obsidian://open?{query}"


EXCALIDRAW_TYPE = "excalidraw"
EXCALIDRAW_VERSION = 2
EXCALIDRAW_SOURCE = "https://github.com/khanh-an-569/driftnote"


def build_excalidraw_document(
    outline: ValidatedOutline, positions: dict[str, NodePosition], *, vault_name: str
) -> dict[str, Any]:
    elements: list[dict[str, Any]] = []
    rectangles_by_id: dict[str, dict[str, Any]] = {}

    root_pos = positions["__root__"]
    root_rect = build_rectangle("root", root_pos, depth=0, action="full")
    elements.append(root_rect)
    rectangles_by_id["root"] = root_rect
    elements.append(build_text("root-text", "root", root_pos, outline.title))

    def add_arrow(parent_id: str, node_id: str, parent_pos: NodePosition, pos: NodePosition) -> None:
        arrow_id = f"{parent_id}->{node_id}"
        arrow = build_arrow(arrow_id, parent_id, node_id, parent_pos, pos)
        elements.append(arrow)
        binding_entry = {"id": arrow_id, "type": "arrow"}
        rectangles_by_id[parent_id]["boundElements"].append(binding_entry)
        rectangles_by_id[node_id]["boundElements"].append(binding_entry)

    def walk(node: OutlineNode, parent_id: str, parent_pos: NodePosition) -> None:
        pos = positions[node.id]
        rect = build_rectangle(node.id, pos, depth=node.depth, action=node.action)
        elements.append(rect)
        rectangles_by_id[node.id] = rect
        elements.append(build_text(f"{node.id}-text", node.id, pos, node.text))
        if node.action in ("condensed", "link"):
            elements[-2]["link"] = build_obsidian_uri(
                vault_name, outline.source_note_path, node.source_anchor
            )
        add_arrow(parent_id, node.id, parent_pos, pos)
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
            temp_path = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

        if target_path.exists():
            if not regenerate:
                raise MindmapError(
                    f"{target_path} already exists. Pass --regenerate to overwrite it."
                )
            os.replace(temp_path, target_path)
            temp_path = None
            return "regenerated"

        try:
            os.link(temp_path, target_path)
        except FileExistsError as exc:
            raise MindmapError(
                f"{target_path} already exists. Pass --regenerate to overwrite it."
            ) from exc
        except OSError as exc:
            raise MindmapError(
                f"This filesystem cannot publish {target_path.name} without overwrite risk "
                "(hard links are unsupported here)."
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
            temp_path = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
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
            "Path to driftnote.yaml to read an 'excalidraw_output_dir' default from. "
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
    try:
        note_path.relative_to(vault)
    except ValueError as exc:
        raise MindmapError(f"Source note must be inside the vault: {note_path}") from exc
    if not note_path.is_file():
        raise MindmapError(f"Source note does not exist: {note_path}")

    positions = (
        compute_radial_layout(outline) if outline.layout == "radial" else compute_tree_layout(outline)
    )
    document = build_excalidraw_document(outline, positions, vault_name=vault.name)

    output_dir_value = args.output_dir
    if not output_dir_value and args.config_file:
        output_dir_value = _config_value(Path(args.config_file), "excalidraw_output_dir")
    output_dir = (vault / output_dir_value).resolve() if output_dir_value else note_path.parent
    if output_dir_value:
        try:
            output_dir.relative_to(vault)
        except ValueError as exc:
            raise MindmapError(f"Output directory must be inside the vault: {output_dir}") from exc
    diagram_filename = f"{note_path.stem}.excalidraw"
    target_path = output_dir / diagram_filename

    status = write_excalidraw_file(document, target_path, regenerate=args.regenerate)

    linked = False
    if not args.no_link_back:
        linked = append_diagram_link(note_path, diagram_filename)

    exported_to = None
    export_error = None
    if args.export_dir:
        try:
            export_path = Path(args.export_dir).expanduser().resolve() / diagram_filename
            write_excalidraw_file(document, export_path, regenerate=args.regenerate)
            exported_to = str(export_path)
        except (MindmapError, OSError, ValueError) as exc:
            export_error = str(exc)

    return {
        "status": status,
        "path": str(target_path),
        "linked_from_note": linked,
        "exported_to": exported_to,
        "export_error": export_error,
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
