#!/usr/bin/env python3
"""Turn a strictly source-derived outline into a brainstorm-style Excalidraw diagram."""

from __future__ import annotations

import math
import urllib.parse
import zlib
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
