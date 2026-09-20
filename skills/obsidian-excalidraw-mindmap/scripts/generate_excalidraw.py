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
