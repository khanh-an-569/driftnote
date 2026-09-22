#!/usr/bin/env python3
"""Create a duplicate-safe Obsidian source note from browser or Tavily content.

The script uses only the Python standard library. It never accepts an API key
as an argument; optional Tavily extraction reads TAVILY_API_KEY from the
process environment or a local .env file.
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import ipaddress
import json
import os
import re
import secrets
import socket
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


TRACKING_PARAMETERS = {
    "dclid",
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "mkt_tok",
    "ref_src",
    "si",
    "vero_conv",
    "vero_id",
}
SENSITIVE_QUERY_PARTS = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "code",
    "credential",
    "key",
    "password",
    "session",
    "sig",
    "signature",
    "token",
}
IDENTITY_LOCK_DIRECTORY = ".web-to-obsidian-locks"
IDENTITY_LOCK_TIMEOUT_SECONDS = 10.0
IDENTITY_LOCK_POLL_SECONDS = 0.05
SKIP_DIRECTORIES = {
    ".git",
    ".obsidian",
    ".trash",
    IDENTITY_LOCK_DIRECTORY,
    "node_modules",
    "__pycache__",
}
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
CONTENT_TYPES = ("article", "news", "bookmark", "music", "video", "podcast", "social", "other")
CAPTURE_METHODS = (
    "selection",
    "chrome",
    "tavily-basic",
    "tavily-advanced",
    "hybrid",
    "manual",
    "public-html",
)
ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
CSS_CLASS_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SKILL_VAULT_ENV_NAME = "WEB_TO_OBSIDIAN_VAULT_PATH"
LEGACY_VAULT_ENV_NAME = "OBSIDIAN_VAULT_PATH"
ALLOWED_DOTENV_NAMES = {
    SKILL_VAULT_ENV_NAME,
    LEGACY_VAULT_ENV_NAME,
    "TAVILY_API_KEY",
}
SENSITIVE_QUERY_PREFIXES = ("x-amz-", "x-goog-")
SOURCE_CONTENT_START = "<!-- web-to-obsidian:source-content:start -->"
SOURCE_CONTENT_END = "<!-- web-to-obsidian:source-content:end -->"
PERSONAL_NOTES_START = "<!-- web-to-obsidian:personal-notes:start -->"


class CaptureError(RuntimeError):
    """A safe, user-facing capture failure."""


class TavilyConfigurationError(CaptureError):
    """Tavily cannot run because local credentials are unavailable."""


@dataclass(frozen=True)
class TavilyResult:
    content: str
    depth: str
    request_id: str | None


@dataclass(frozen=True)
class SafeUrl:
    source_url: str
    canonical_url: str
    legacy_canonical_url: str
    redacted: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class NoteIdentity:
    path: Path
    source_id: str
    source_url: str
    canonical_url: str
    canonicalization_version: str


@dataclass
class HtmlNode:
    tag: str
    attrs: dict[str, str]
    children: list[object]


class _HtmlTreeParser(HTMLParser):
    """Small dependency-free HTML tree builder for browser-authorized DOM."""

    _VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = HtmlNode("document", {}, [])
        self.stack = [self.root]

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        node = HtmlNode(
            tag.lower(),
            {name.lower(): value or "" for name, value in attrs},
            [],
        )
        self.stack[-1].children.append(node)
        if node.tag not in self._VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)
        if self.stack[-1].tag == tag.lower():
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        wanted = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == wanted:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


class _HtmlMarkdownRenderer:
    _CALLOUT_TYPES = {
        "chapter-connection": "info",
        "checkpoint": "success",
        "definition": "quote",
        "example": "example",
        "learning-objectives": "abstract",
        "lighthouse": "tip",
        "notebook": "example",
        "perspective": "info",
        "quiz-answer": "example",
        "quiz-question": "question",
        "takeaways": "tip",
        "war-story": "warning",
    }
    _IGNORED_TAGS = {
        "base",
        "button",
        "canvas",
        "form",
        "iframe",
        "input",
        "link",
        "meta",
        "nav",
        "noscript",
        "script",
        "style",
        "svg",
        "template",
    }
    _IGNORED_IDS = {
        "quarto-back-to-top",
    }
    _SAFE_FALLBACK_TAGS = {
        "a",
        "b",
        "br",
        "caption",
        "code",
        "col",
        "colgroup",
        "em",
        "i",
        "img",
        "p",
        "span",
        "strong",
        "sub",
        "sup",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
    }
    _SAFE_FALLBACK_ATTRIBUTES = {
        "a": {"href", "title"},
        "col": {"span"},
        "img": {"alt", "height", "src", "title", "width"},
        "td": {"colspan", "headers", "rowspan"},
        "th": {"colspan", "headers", "rowspan", "scope"},
    }

    def __init__(self, base_url: str, *, heading_offset: int = 0) -> None:
        self.base_url = base_url
        self.heading_offset = max(0, heading_offset)

    def render(self, node: HtmlNode | str) -> str:
        if isinstance(node, str):
            value = re.sub(r"\s+", " ", node)
            return re.sub(r"(?<!\\)\$(?=\d)", r"\\$", value)
        if node.attrs.get("id") in self._IGNORED_IDS:
            return ""
        if node.tag == "header" and (
            node.attrs.get("id") == "title-block-header"
            or "quarto-title-block" in node.attrs.get("class", "").split()
        ):
            return self._render_title_block(node)
        if node.tag in self._IGNORED_TAGS:
            return ""

        math = self._render_math(node)
        if math is not None:
            return math

        tag = node.tag
        if tag in {"document", "html", "body", "main", "article", "section"}:
            return self._block_children(node)
        if tag in {"div", "header", "footer", "aside", "nav"}:
            return self._block_children(node)
        if re.fullmatch(r"h[1-6]", tag):
            level = min(6, int(tag[1]) + self.heading_offset)
            return f"{'#' * level} {self._inline_children(node).strip()}\n\n"
        if tag == "p":
            return f"{self._inline_children(node).strip()}\n\n"
        if tag == "br":
            return "  \n"
        if tag == "hr":
            return "\n---\n\n"
        if tag in {"strong", "b"}:
            value = self._inline_children(node).strip()
            return f"**{value}**" if value else ""
        if tag in {"em", "i"}:
            value = self._inline_children(node).strip()
            return f"*{value}*" if value else ""
        if tag in {"del", "s", "strike"}:
            value = self._inline_children(node).strip()
            return f"~~{value}~~" if value else ""
        if tag == "mark":
            value = self._inline_children(node).strip()
            return f"=={value}==" if value else ""
        if tag == "a":
            label = self._inline_children(node).strip()
            target = self._resolve_url(node.attrs.get("href", ""), image=False)
            if not target:
                return label
            image_children = [
                child
                for child in node.children
                if isinstance(child, HtmlNode) and child.tag == "img"
            ]
            if len(image_children) == 1:
                image_target = self._image_target(image_children[0])
                target_name = Path(urllib.parse.urlsplit(target).path).name
                image_name = Path(urllib.parse.urlsplit(image_target).path).name
                classes = set(node.attrs.get("class", "").split())
                if image_target and (
                    "lightbox" in classes
                    or (target_name and target_name == image_name and target != image_target)
                ):
                    target = image_target
            return f"[{label or target}]({self._markdown_destination(target)})"
        if tag == "img":
            target = self._image_target(node)
            if not target:
                return ""
            alt = node.attrs.get("alt", "").replace("]", "\\]").strip()
            title = node.attrs.get("title", "").replace('"', "\\\"").strip()
            suffix = f' "{title}"' if title else ""
            return f"![{alt}]({self._markdown_destination(target)}{suffix})"
        if tag == "figure":
            content: list[str] = []
            for child in node.children:
                if isinstance(child, HtmlNode) and child.tag == "figcaption":
                    caption = self._inline_children(child).strip()
                    if caption:
                        content.append(f"*{caption}*")
                else:
                    rendered = self.render(child).strip()
                    if rendered:
                        content.append(rendered)
            return "\n\n".join(content) + ("\n\n" if content else "")
        if tag == "figcaption":
            value = self._inline_children(node).strip()
            return f"*{value}*" if value else ""
        if tag == "code" and not self._has_ancestor_hint(node, "pre"):
            value = self._text_content(node).strip()
            fence = "``" if "`" in value else "`"
            return f"{fence}{value}{fence}" if value else ""
        if tag == "pre":
            value = self._text_content(node).strip("\n")
            language = ""
            for child in node.children:
                if isinstance(child, HtmlNode) and child.tag == "code":
                    classes = child.attrs.get("class", "").split()
                    language = next(
                        (item.removeprefix("language-") for item in classes if item.startswith("language-")),
                        "",
                    )
                    break
            fence = "````" if "```" in value else "```"
            return f"{fence}{language}\n{value}\n{fence}\n\n"
        if tag in {"ul", "ol"}:
            return self._render_list(node)
        if tag == "li":
            return self._inline_children(node).strip()
        if tag == "blockquote":
            value = self._block_children(node).strip()
            return "\n".join(f"> {line}" if line else ">" for line in value.splitlines()) + "\n\n"
        if tag == "table":
            return self._render_table(node)
        if tag == "details":
            return self._render_details(node)
        if tag == "summary":
            return self._inline_children(node)
        if tag == "dl":
            return self._block_children(node)
        if tag == "dt":
            return f"**{self._inline_children(node).strip()}**\n"
        if tag == "dd":
            return f": {self._inline_children(node).strip()}\n\n"
        return self._inline_children(node)

    def _has_ancestor_hint(self, node: HtmlNode, tag: str) -> bool:
        # The tree intentionally has no parent references. Code within pre is handled
        # by the pre renderer before a child renderer is invoked.
        return False

    def _inline_children(self, node: HtmlNode) -> str:
        return self._join_children(node, skip_blank_text=False)

    def _block_children(self, node: HtmlNode) -> str:
        value = self._join_children(node, skip_blank_text=True)
        return value + ("\n\n" if value.strip() and not value.endswith("\n\n") else "")

    def _join_children(self, node: HtmlNode, *, skip_blank_text: bool) -> str:
        parts: list[str] = []
        for child in node.children:
            if skip_blank_text and isinstance(child, str) and not child.strip():
                continue
            rendered = self.render(child)
            if parts and parts[-1].endswith("\n\n"):
                rendered = rendered.lstrip(" \t")
            parts.append(rendered)
        return "".join(parts)

    def _text_content(self, node: HtmlNode | str) -> str:
        if isinstance(node, str):
            return node
        if node.tag in self._IGNORED_TAGS:
            return ""
        return "".join(self._text_content(child) for child in node.children)

    def _resolve_url(self, value: str, *, image: bool) -> str:
        raw = html_lib.unescape(value).strip()
        if not raw:
            return ""
        resolved = urllib.parse.urljoin(self.base_url, raw)
        parsed = urllib.parse.urlsplit(resolved)
        allowed = {"http", "https"} if image else {"http", "https", "mailto", "tel"}
        if parsed.scheme.lower() not in allowed:
            return ""
        return urllib.parse.quote(
            resolved,
            safe=":/?#[]@!$&'*,;=+%~-._",
        )

    def _markdown_destination(self, value: str) -> str:
        if any(character.isspace() for character in value):
            return f"<{value}>"
        return value

    def _image_target(self, node: HtmlNode) -> str:
        source = (
            node.attrs.get("src")
            or node.attrs.get("data-src")
            or node.attrs.get("data-original")
            or ""
        )
        return self._resolve_url(source, image=True)

    def _render_title_block(self, node: HtmlNode) -> str:
        headings = self._descendants(node, "h1")
        title_node = next(
            (
                heading
                for heading in headings
                if "title" in heading.attrs.get("class", "").split()
            ),
            headings[0] if headings else None,
        )
        title = self._text_content(title_node).strip() if title_node else "Source"
        breadcrumbs: list[str] = []
        for link in self._descendants(node, "a"):
            label = self._text_content(link).strip()
            target = self._resolve_url(link.attrs.get("href", ""), image=False)
            if label and target:
                breadcrumbs.append(
                    f"[{label}]({self._markdown_destination(target)})"
                )
        lines = [f"> [!web-header] {title or 'Source'}"]
        if breadcrumbs:
            lines.append(f"> {' · '.join(breadcrumbs)}")
        return "\n".join(lines) + "\n\n"

    def _render_list(self, node: HtmlNode, depth: int = 0) -> str:
        ordered = node.tag == "ol"
        lines: list[str] = []
        index = 1
        for child in node.children:
            if not isinstance(child, HtmlNode) or child.tag != "li":
                continue
            inline_parts: list[str] = []
            nested_parts: list[str] = []
            for item in child.children:
                if isinstance(item, HtmlNode) and item.tag in {"ul", "ol"}:
                    nested_parts.append(self._render_list(item, depth + 1).rstrip())
                else:
                    inline_parts.append(self.render(item))
            prefix = f"{index}." if ordered else "-"
            value = "".join(inline_parts).strip()
            lines.append(f"{'  ' * depth}{prefix} {value}")
            lines.extend(part for part in nested_parts if part)
            index += 1
        return "\n".join(lines) + ("\n\n" if lines else "")

    def _descendants(self, node: HtmlNode, tag: str) -> list[HtmlNode]:
        matches: list[HtmlNode] = []
        for child in node.children:
            if not isinstance(child, HtmlNode):
                continue
            if child.tag == tag:
                matches.append(child)
            elif child.tag != "table":
                matches.extend(self._descendants(child, tag))
        return matches

    def _render_table(self, node: HtmlNode) -> str:
        rows: list[list[str]] = []
        header_index: int | None = None
        for row in self._descendants(node, "tr"):
            cells = [
                child
                for child in row.children
                if isinstance(child, HtmlNode) and child.tag in {"th", "td"}
            ]
            if not cells:
                continue
            if any(cell.attrs.get("rowspan", "1") not in {"", "1"} for cell in cells) or any(
                cell.attrs.get("colspan", "1") not in {"", "1"} for cell in cells
            ):
                return self._serialize_safe_html(node) + "\n\n"
            if header_index is None and any(cell.tag == "th" for cell in cells):
                header_index = len(rows)
            rendered_cells: list[str] = []
            for cell in cells:
                value = self._inline_children(cell).strip()
                value = re.sub(r"\s*\n\s*", "<br>", value).replace("|", "\\|")
                rendered_cells.append(value)
            rows.append(rendered_cells)

        if not rows:
            return ""
        width = max(len(row) for row in rows)
        rows = [row + [""] * (width - len(row)) for row in rows]
        if header_index is None:
            header = [""] * width
            body = rows
        else:
            header = rows[header_index]
            body = rows[:header_index] + rows[header_index + 1 :]
        lines = [
            f"| {' | '.join(header)} |",
            f"| {' | '.join('---' for _ in range(width))} |",
            *[f"| {' | '.join(row)} |" for row in body],
        ]
        return "\n".join(lines) + "\n\n"

    def _serialize_safe_html(self, node: HtmlNode | str) -> str:
        if isinstance(node, str):
            return html_lib.escape(node)
        if node.tag in self._IGNORED_TAGS:
            return ""
        inner = "".join(self._serialize_safe_html(child) for child in node.children)
        if node.tag not in self._SAFE_FALLBACK_TAGS:
            return inner
        attrs: list[str] = []
        allowed_attributes = self._SAFE_FALLBACK_ATTRIBUTES.get(node.tag, set())
        for name, value in node.attrs.items():
            if name not in allowed_attributes:
                continue
            if name in {"href", "src", "poster", "cite"}:
                value = self._resolve_url(
                    value,
                    image=name in {"src", "poster"},
                )
                if not value:
                    continue
            attrs.append(f' {name}="{html_lib.escape(value, quote=True)}"')
        if node.tag in _HtmlTreeParser._VOID_TAGS:
            return f"<{node.tag}{''.join(attrs)}>"
        return f"<{node.tag}{''.join(attrs)}>{inner}</{node.tag}>"

    def _render_details(self, node: HtmlNode) -> str:
        summary = "Details"
        body: list[str] = []
        for child in node.children:
            if isinstance(child, HtmlNode) and child.tag == "summary":
                summary = self._text_content(child).strip() or summary
            else:
                rendered = self.render(child).strip()
                if rendered:
                    body.append(rendered)
        classes = set(node.attrs.get("class", "").split())
        source_type = next(
            (
                item.removeprefix("callout-")
                for item in classes
                if item.startswith("callout-")
                and item.removeprefix("callout-") in self._CALLOUT_TYPES
            ),
            "",
        )
        if source_type:
            callout_type = self._CALLOUT_TYPES[source_type]
        elif summary.lower().startswith("checkpoint"):
            callout_type = "success"
        elif summary.lower().startswith("self-check"):
            callout_type = "question"
        elif summary.lower().startswith("learning objectives"):
            callout_type = "abstract"
        else:
            callout_type = "note"
        fold_state = "+" if "open" in node.attrs else "-"
        lines = [f"> [!{callout_type}]{fold_state} {summary}"]
        inner = "\n\n".join(body)
        if inner:
            for line in inner.splitlines():
                lines.append(f"> {line}" if line else ">")
        return "\n".join(lines) + "\n\n"

    def _render_math(self, node: HtmlNode) -> str | None:
        classes = set(node.attrs.get("class", "").split())
        if node.tag == "math":
            annotations = self._descendants(node, "annotation")
            tex = next(
                (
                    self._text_content(item).strip()
                    for item in annotations
                    if item.attrs.get("encoding", "").lower() in {"application/x-tex", "text/x-tex"}
                ),
                "",
            )
            if not tex:
                return None
            display = node.attrs.get("display", "").lower() == "block"
            return "\n\n$$\n" + tex + "\n$$\n\n" if display else "$" + tex + "$"
        if "math" not in classes:
            return None
        raw = self._text_content(node).strip()
        display = "display" in classes or raw.startswith("\\[")
        raw = re.sub(r"^\\\(|\\\)$", "", raw).strip()
        raw = re.sub(r"^\\\[|\\\]$", "", raw).strip()
        if not raw:
            return ""
        return "\n\n$$\n" + raw + "\n$$\n\n" if display else "$" + raw + "$"


def _find_html_node(root: HtmlNode, predicate: object) -> HtmlNode | None:
    if callable(predicate) and predicate(root):
        return root
    for child in root.children:
        if isinstance(child, HtmlNode):
            match = _find_html_node(child, predicate)
            if match:
                return match
    return None


def _direct_children(node: HtmlNode, tag: str) -> list[HtmlNode]:
    return [
        child
        for child in node.children
        if isinstance(child, HtmlNode) and child.tag == tag
    ]


def _toc_heading_for_fragment(
    selected: HtmlNode,
    fragment: str,
    renderer: _HtmlMarkdownRenderer,
) -> str:
    target = _find_html_node(
        selected,
        lambda node: (
            node.attrs.get("id") == fragment
            or node.attrs.get("data-anchor-id") == fragment
        ),
    )
    if target is None:
        return ""
    heading = (
        target
        if re.fullmatch(r"h[1-6]", target.tag)
        else _find_html_node(target, lambda node: bool(re.fullmatch(r"h[1-6]", node.tag)))
    )
    return renderer._text_content(heading).strip() if heading else ""


def _escape_wikilink(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("]", "\\]")


def _render_toc_list(
    list_node: HtmlNode,
    selected: HtmlNode,
    renderer: _HtmlMarkdownRenderer,
    *,
    ancestors: tuple[str, ...] = (),
    depth: int = 0,
) -> list[str]:
    lines: list[str] = []
    for item in _direct_children(list_node, "li"):
        links = _direct_children(item, "a")
        nested_lists = _direct_children(item, "ul")
        if not links:
            continue
        link = links[0]
        href = html_lib.unescape(link.attrs.get("href", "")).strip()
        if not href.startswith("#") or len(href) == 1:
            continue
        fragment = urllib.parse.unquote(href[1:])
        heading = _toc_heading_for_fragment(selected, fragment, renderer)
        if not heading:
            continue
        label = renderer._text_content(link).strip() or heading
        path = (*ancestors, heading)
        destination = "#" + "#".join(_escape_wikilink(part) for part in path)
        escaped_label = _escape_wikilink(label)
        if len(path) == 1 and label == heading:
            wikilink = f"[[{destination}]]"
        else:
            wikilink = f"[[{destination}|{escaped_label}]]"
        lines.append(f"{'  ' * depth}- {wikilink}")
        for nested in nested_lists:
            lines.extend(
                _render_toc_list(
                    nested,
                    selected,
                    renderer,
                    ancestors=path,
                    depth=depth + 1,
                )
            )
    return lines


def _render_toc_callout(
    root: HtmlNode,
    selected: HtmlNode,
    renderer: _HtmlMarkdownRenderer,
) -> str:
    toc = _find_html_node(
        root,
        lambda node: (
            node.tag == "nav"
            and (
                node.attrs.get("id", "").lower() == "toc"
                or node.attrs.get("role", "").lower() == "doc-toc"
            )
        ),
    )
    if toc is None:
        return ""
    toc_lists = _direct_children(toc, "ul")
    if not toc_lists:
        return ""
    items: list[str] = []
    for toc_list in toc_lists:
        items.extend(_render_toc_list(toc_list, selected, renderer))
    if not items:
        return ""
    title_node = next(
        (
            child
            for child in toc.children
            if isinstance(child, HtmlNode) and re.fullmatch(r"h[1-6]", child.tag)
        ),
        None,
    )
    title = renderer._text_content(title_node).strip() if title_node else ""
    lines = [f"> [!toc]- {title or 'Table of contents'}"]
    lines.extend(f"> {line}" for line in items)
    return "\n".join(lines)


def _insert_toc_after_header(markdown: str, toc: str) -> str:
    if not toc:
        return markdown
    if markdown.startswith("> [!web-header]"):
        boundary = markdown.find("\n\n")
        if boundary >= 0:
            return markdown[:boundary] + "\n\n" + toc + "\n\n" + markdown[boundary + 2 :]
    return toc + "\n\n" + markdown


_MARKDOWN_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_CODE_FENCE_PATTERN = re.compile(r"^```")


def _extract_markdown_headings(content: str) -> list[tuple[int, str]]:
    headings: list[tuple[int, str]] = []
    in_code_fence = False
    for line in content.splitlines():
        if _CODE_FENCE_PATTERN.match(line):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        match = _MARKDOWN_HEADING_PATTERN.match(line)
        if match:
            headings.append((len(match.group(1)), match.group(2).strip()))
    return headings


def _generate_toc_from_headings(content: str) -> str:
    """Fallback TOC: synthesize one from the content's own headings.

    Only runs when no native page TOC was already cloned into ``content``
    and there are enough headings to make navigation useful.
    """
    if "[!toc]" in content:
        return ""
    headings = _extract_markdown_headings(content)
    if len(headings) < 3:
        return ""

    lines: list[str] = []
    stack: list[tuple[int, str]] = []
    for level, text in headings:
        while stack and stack[-1][0] >= level:
            stack.pop()
        ancestors = tuple(entry[1] for entry in stack)
        path = ancestors + (text,)
        stack.append((level, text))
        destination = "#" + "#".join(_escape_wikilink(part) for part in path)
        escaped_text = _escape_wikilink(text)
        if len(path) == 1:
            wikilink = f"[[{destination}]]"
        else:
            wikilink = f"[[{destination}|{escaped_text}]]"
        depth = len(path) - 1
        lines.append(f"{'  ' * depth}- {wikilink}")

    toc_lines = ["> [!toc]- Table of contents"]
    toc_lines.extend(f"> {line}" for line in lines)
    return "\n".join(toc_lines)


def _find_unfenced_multiline_code_spans(content: str) -> list[tuple[int, int]]:
    """Report 1-indexed line ranges where a lone backtick code span crosses a
    blank line. A real ``` fence always closes before content resumes; a
    single backtick that survives a blank-line paragraph break never really
    closed, so everything inside — including shell comments that look like
    "# Step 2" — gets parsed as ordinary Markdown, not code.
    """

    spans: list[tuple[int, int]] = []
    in_triple_fence = False
    open_span_start: int | None = None
    saw_blank_since_open = False

    lines = content.splitlines()
    for line_number, line in enumerate(lines, start=1):
        if _CODE_FENCE_PATTERN.match(line):
            in_triple_fence = not in_triple_fence
            continue
        if in_triple_fence:
            continue
        if open_span_start is not None and not line.strip():
            saw_blank_since_open = True
        if line.count("`") % 2 == 1:
            if open_span_start is None:
                open_span_start = line_number
                saw_blank_since_open = False
            else:
                if saw_blank_since_open:
                    spans.append((open_span_start, line_number))
                open_span_start = None
                saw_blank_since_open = False
    if open_span_start is not None:
        spans.append((open_span_start, len(lines)))
    return spans


def _extract_toc_block(content: str) -> str:
    """Return only the ``> [!toc]`` callout's lines, or "" if there is none."""

    lines = content.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("> [!toc]")), None)
    if start is None:
        return ""
    end = start + 1
    while end < len(lines) and lines[end].startswith(">"):
        end += 1
    return "\n".join(lines[start:end])


_TOC_WIKILINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def _find_duplicate_toc_destinations(toc: str) -> list[str]:
    """Return wikilink destinations that appear more than once in ``toc``."""

    seen: dict[str, int] = {}
    for match in _TOC_WIKILINK_PATTERN.finditer(toc):
        destination = match.group(1)
        seen[destination] = seen.get(destination, 0) + 1
    return sorted(destination for destination, count in seen.items() if count > 1)


def _find_empty_sections(content: str) -> list[str]:
    """Report heading text for a section with no body before the next
    sibling/ancestor heading or end of content. A heading immediately
    followed by a deeper child heading is not empty — the child is its body.
    """

    lines = content.splitlines()
    headings: list[tuple[int, int, str]] = []
    in_fence = False
    for index, line in enumerate(lines):
        if _CODE_FENCE_PATTERN.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _MARKDOWN_HEADING_PATTERN.match(line)
        if match:
            headings.append((index, len(match.group(1)), match.group(2).strip()))

    empty: list[str] = []
    for position, (line_index, level, text) in enumerate(headings):
        if position + 1 < len(headings):
            next_index, next_level, _ = headings[position + 1]
        else:
            next_index, next_level = len(lines), None
        if next_level is not None and next_level > level:
            continue
        has_body = False
        fence_state = False
        for body_line in lines[line_index + 1 : next_index]:
            if _CODE_FENCE_PATTERN.match(body_line):
                fence_state = not fence_state
                has_body = True
                continue
            if fence_state:
                has_body = True
                continue
            if body_line.strip():
                has_body = True
        if not has_body:
            empty.append(text)
    return empty


_UPDATE_DATE_PATTERN = re.compile(
    r"(?:C[aậ]p nh[aậ]t l[aầ]n g[aầ]n đ[aâ]y nh[aấ]t|Last updated)\s*:\s*"
    r"(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


def _extract_reported_update_date(content: str) -> str | None:
    """Best-effort extraction of a page's self-reported last-updated date,
    for visibility only — never used to block a write.
    """

    match = _UPDATE_DATE_PATTERN.search(content)
    return match.group(1) if match else None


_HTML_STRUCTURAL_TAG_PATTERN = re.compile(r"<(pre|table|h[1-6])\b", re.IGNORECASE)
_MARKDOWN_TABLE_ROW_PATTERN = re.compile(r"^\s*\|.*\|\s*$")


def _count_html_structural_elements(html: str) -> dict[str, int]:
    counts = {"pre": 0, "table": 0, "heading": 0}
    for match in _HTML_STRUCTURAL_TAG_PATTERN.finditer(html):
        tag = match.group(1).lower()
        if tag == "pre":
            counts["pre"] += 1
        elif tag == "table":
            counts["table"] += 1
        else:
            counts["heading"] += 1
    return counts


def _count_markdown_structural_elements(content: str) -> dict[str, int]:
    counts = {"pre": 0, "table": 0, "heading": 0}
    in_fence = False
    previous_was_table_row = False
    for line in content.splitlines():
        if _CODE_FENCE_PATTERN.match(line):
            if not in_fence:
                counts["pre"] += 1
            in_fence = not in_fence
            previous_was_table_row = False
            continue
        if in_fence:
            continue
        if _MARKDOWN_HEADING_PATTERN.match(line):
            counts["heading"] += 1
            previous_was_table_row = False
            continue
        is_table_row = bool(_MARKDOWN_TABLE_ROW_PATTERN.match(line))
        if is_table_row and not previous_was_table_row:
            counts["table"] += 1
        previous_was_table_row = is_table_row
    return counts


def _find_structural_content_loss(html: str, content: str) -> list[str]:
    """Compare structural element counts between source HTML and the
    converted Markdown, to catch content silently dropped inside
    html_to_markdown() itself — a different failure mode than a malformed
    Markdown input (Tasks 1-4), which only validates Markdown that has
    already been produced.
    """

    html_counts = _count_html_structural_elements(html)
    markdown_counts = _count_markdown_structural_elements(content)
    labels = {"pre": "code block", "table": "table", "heading": "heading"}
    issues: list[str] = []
    for key, label in labels.items():
        if markdown_counts[key] < html_counts[key]:
            issues.append(
                f"Conversion lost {html_counts[key] - markdown_counts[key]} "
                f"{label}(s): {html_counts[key]} in the source HTML, only "
                f"{markdown_counts[key]} in the converted Markdown."
            )
    return issues


def _collect_content_review_issues(
    content: str, *, source_html: str | None = None
) -> list[str]:
    """Return blocking reasons the generated source content should not be
    published as-is. An empty list means the content passed validation.
    """

    issues: list[str] = []

    for start_line, end_line in _find_unfenced_multiline_code_spans(content):
        issues.append(
            f"A single backtick opened on line {start_line} is not closed "
            f"before line {end_line}; the code fence is broken and any "
            "headings inside it were likely misread as real headings."
        )

    for destination in _find_duplicate_toc_destinations(_extract_toc_block(content)):
        issues.append(
            f"Table of contents entry `{destination}` appears more than once; "
            "Obsidian cannot navigate to a unique heading for it."
        )

    for heading in _find_empty_sections(content):
        issues.append(
            f'Section "{heading}" has no body content before the next heading.'
        )

    if source_html:
        issues.extend(_find_structural_content_loss(source_html, content))

    return issues


def html_to_markdown(html: str, base_url: str, *, heading_offset: int = 0) -> str:
    """Convert browser-authorized HTML into Obsidian-friendly Markdown."""

    parser = _HtmlTreeParser()
    parser.feed(html)
    parser.close()
    root = parser.root
    selected = (
        _find_html_node(root, lambda node: node.tag == "article")
        or _find_html_node(root, lambda node: node.tag == "main")
        or _find_html_node(root, lambda node: node.attrs.get("role", "").lower() == "main")
        or _find_html_node(root, lambda node: node.tag == "body")
        or root
    )
    renderer = _HtmlMarkdownRenderer(
        base_url,
        heading_offset=heading_offset,
    )
    markdown = renderer.render(selected)
    toc = _render_toc_callout(root, selected, renderer)
    markdown = _insert_toc_after_header(markdown, toc)
    markdown = re.sub(r"[ \t]+\n", "\n", markdown)
    markdown = re.sub(r"(?m)^ {1,3}(?=#{1,6}\s)", "", markdown)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip()


def _looks_like_html_capture(content: str) -> bool:
    """Recognize HTML markup in raw capture data, ignoring fenced code examples."""

    outside_fences = re.sub(
        r"(?ms)^ {0,3}(?:`{3,}|~{3,})[^\n]*\n.*?^ {0,3}(?:`{3,}|~{3,})[ \t]*$",
        "",
        content,
    )
    paired_element = re.search(
        r"(?is)<(?P<tag>html|body|main|article|section|div|p|h[1-6]|"
        r"ul|ol|li|table|figure|details)\b[^>]*>.*?</(?P=tag)\s*>",
        outside_fences,
    )
    linked_element = re.search(
        r"(?is)<a\b[^>]*\bhref\s*=\s*[^>]+>.*?</a\s*>",
        outside_fences,
    )
    if paired_element:
        return True
    if re.search(r"(?m)^[ \t]{0,3}#{1,6}\s|^[ \t]{0,3}(?:[-*+]\s|\d+\.\s)", outside_fences):
        return False
    return bool(linked_element)

def _dotenv_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
        return value[1:-1]
    comment = re.search(r"\s+#", value)
    if comment:
        value = value[: comment.start()].rstrip()
    return value


def _central_env_path(script_path: Path | None = None) -> Path | None:
    source_path = (script_path or Path(__file__)).expanduser().resolve()
    for parent in source_path.parents:
        if parent.name.lower() == "skills":
            return (parent.parent / ".env").resolve()
    return None


def load_dotenv(
    path_value: str | None = None,
    *,
    workspace: Path | None = None,
    script_path: Path | None = None,
) -> Path | None:
    """Load workspace and central .env files without overriding process variables."""

    base = (workspace or Path.cwd()).expanduser().resolve()
    if path_value:
        explicit_path = Path(path_value).expanduser()
        if not explicit_path.is_absolute():
            explicit_path = base / explicit_path
        env_paths = [explicit_path.resolve()]
    else:
        env_paths = [(base / ".env").resolve()]
        central_path = _central_env_path(script_path)
        if central_path and central_path not in env_paths:
            env_paths.append(central_path)

    first_loaded: Path | None = None
    for env_path in env_paths:
        if not env_path.exists():
            if path_value:
                raise CaptureError(f"Environment file does not exist: {env_path}")
            continue
        if not env_path.is_file():
            raise CaptureError(f"Environment file is not a file: {env_path}")
        if first_loaded is None:
            first_loaded = env_path

        for line_number, raw_line in enumerate(
            env_path.read_text(encoding="utf-8-sig").splitlines(),
            start=1,
        ):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            if "=" not in line:
                raise CaptureError(
                    f"Invalid .env assignment at {env_path}:{line_number}"
                )
            name, raw_value = line.split("=", 1)
            name = name.strip()
            if not ENV_NAME_PATTERN.fullmatch(name):
                raise CaptureError(
                    f"Invalid .env variable name at {env_path}:{line_number}"
                )
            if name in ALLOWED_DOTENV_NAMES:
                os.environ.setdefault(name, _dotenv_value(raw_value))
    return first_loaded


def _vault_from_yaml(config_path: Path) -> str | None:
    if not config_path.is_file():
        return None
    for raw_line in config_path.read_text(encoding="utf-8-sig").splitlines():
        match = re.match(r"^\s*vault_root\s*:\s*(.*?)\s*$", raw_line)
        if not match:
            continue
        value = match.group(1).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
            value = value[1:-1]
        return value or None
    return None


def resolve_vault(vault_argument: str | None, *, workspace: Path | None = None) -> str:
    """Resolve CLI, environment, then workspace YAML configuration."""

    if vault_argument and vault_argument.strip():
        return vault_argument.strip()
    for env_name in (SKILL_VAULT_ENV_NAME, LEGACY_VAULT_ENV_NAME):
        env_vault = os.environ.get(env_name, "").strip()
        if env_vault:
            return env_vault
    config_path = (workspace or Path.cwd()) / "driftnote.yaml"
    config_vault = _vault_from_yaml(config_path.resolve())
    if config_vault:
        return config_vault
    raise CaptureError(
        "Obsidian vault is not configured. Use --vault, set "
        "WEB_TO_OBSIDIAN_VAULT_PATH (or OBSIDIAN_VAULT_PATH) in .env, or add "
        "vault_root to driftnote.yaml."
    )


def _normalized_url_parts(value: str) -> tuple[urllib.parse.SplitResult, str, str]:
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise CaptureError("The source URL contains invalid characters.")
    if "\\" in value:
        raise CaptureError("The source URL contains invalid characters.")
    raw = value.strip()
    if any(char in raw for char in ' <>'):
        raise CaptureError("The source URL contains invalid characters.")
    try:
        parsed = urllib.parse.urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise CaptureError("The source URL is invalid.") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise CaptureError("The source URL must be an absolute HTTP(S) URL.")

    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower().rstrip(".")
    try:
        hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise CaptureError("The source URL contains an invalid hostname.") from exc
    display_hostname = f"[{hostname}]" if ":" in hostname else hostname
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{display_hostname}:{port}"
    else:
        netloc = display_hostname
    return parsed, scheme, netloc


def _is_sensitive_query_key(key: str) -> bool:
    normalized = key.lower()
    return (
        normalized in SENSITIVE_QUERY_PARTS
        or any(part in normalized for part in ("token", "secret", "password"))
        or normalized.startswith(SENSITIVE_QUERY_PREFIXES)
    )


def _legacy_canonicalize_url(value: str) -> str:
    parsed, scheme, netloc = _normalized_url_parts(value)

    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"

    kept_query: list[tuple[str, str]] = []
    for key, item_value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        normalized_key = key.lower()
        if normalized_key.startswith("utm_") or normalized_key in TRACKING_PARAMETERS:
            continue
        kept_query.append((key, item_value))
    kept_query.sort(key=lambda item: (item[0].lower(), item[1]))
    query = urllib.parse.urlencode(kept_query, doseq=True)

    return urllib.parse.urlunsplit((scheme, netloc, path, query, ""))


def sanitize_url(value: str) -> SafeUrl:
    """Remove credentials and sensitive query values before storage or hashing."""

    parsed, scheme, netloc = _normalized_url_parts(value)
    reasons: list[str] = []
    if parsed.username is not None or parsed.password is not None:
        reasons.append("embedded_credentials")

    source_query: list[tuple[str, str]] = []
    canonical_query: list[tuple[str, str]] = []
    for key, item_value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        if _is_sensitive_query_key(key):
            if "sensitive_query" not in reasons:
                reasons.append("sensitive_query")
            continue
        source_query.append((key, item_value))
        normalized_key = key.lower()
        if normalized_key.startswith("utm_") or normalized_key in TRACKING_PARAMETERS:
            continue
        canonical_query.append((key, item_value))

    path = parsed.path or "/"
    source_url = urllib.parse.urlunsplit(
        (scheme, netloc, path, urllib.parse.urlencode(source_query, doseq=True), parsed.fragment)
    )
    canonical_url = urllib.parse.urlunsplit(
        (scheme, netloc, path, urllib.parse.urlencode(canonical_query, doseq=True), "")
    )
    return SafeUrl(
        source_url=source_url,
        canonical_url=canonical_url,
        legacy_canonical_url=_legacy_canonicalize_url(source_url),
        redacted=bool(reasons),
        reason_codes=tuple(reasons),
    )


def canonicalize_url(value: str) -> str:
    """Normalize a safe URL without changing path or query ordering semantics."""

    return sanitize_url(value).canonical_url


def _social_platform_for_url(value: str) -> str | None:
    parsed = urllib.parse.urlsplit(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    if host == "instagram.com" or host.endswith(".instagram.com"):
        return "Instagram"
    if host in {"facebook.com", "fb.watch"} or host.endswith(".facebook.com"):
        return "Facebook"
    return None


def _has_query_value(parsed: urllib.parse.SplitResult, key: str) -> bool:
    return any(
        item_key.lower() == key and bool(item_value.strip())
        for item_key, item_value in urllib.parse.parse_qsl(
            parsed.query,
            keep_blank_values=True,
        )
    )


def _looks_like_social_permalink(value: str, platform: str) -> bool:
    parsed = urllib.parse.urlsplit(value)
    parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    lowered = [part.lower() for part in parts]

    if platform == "Instagram":
        if len(parts) >= 2 and lowered[0] in {"p", "reel", "tv"}:
            return bool(parts[1].strip())
        if len(parts) >= 3 and lowered[0] == "stories":
            return bool(parts[1].strip() and parts[2].strip())
        return (
            len(parts) >= 3
            and lowered[0] == "share"
            and lowered[1] in {"p", "reel"}
            and bool(parts[2].strip())
        )

    host = (parsed.hostname or "").lower().rstrip(".")
    if host == "fb.watch":
        return bool(parts)
    if lowered and lowered[0] in {"story.php", "permalink.php"}:
        return _has_query_value(parsed, "story_fbid")
    if lowered and lowered[0] in {"photo.php", "photo"}:
        return _has_query_value(parsed, "fbid")
    if lowered and lowered[0] == "watch":
        return _has_query_value(parsed, "v")
    for marker in ("posts", "reel", "videos"):
        if marker in lowered:
            marker_index = lowered.index(marker)
            if marker_index + 1 < len(parts) and parts[marker_index + 1].strip():
                return True
    return (
        len(parts) >= 3
        and lowered[0] == "share"
        and lowered[1] in {"p", "r", "v"}
        and bool(parts[2].strip())
    )


def _validate_social_permalink(
    source_url: str,
    *,
    content_type: str,
    confirmed: bool,
) -> None:
    if content_type != "social" or confirmed:
        return
    platform = _social_platform_for_url(source_url)
    if platform is None or _looks_like_social_permalink(source_url, platform):
        return
    raise CaptureError(
        f"The {platform} URL is not a recognized post permalink. "
        "Open the post itself or use the post menu and choose Copy link, then "
        "provide that URL. If this unusual URL is the exact post link, ask the "
        "user to confirm it before using --confirm-social-permalink."
    )


def source_id_for(canonical_url: str) -> str:
    return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:16]


def sanitize_filename(title: str, fallback: str, max_length: int = 96) -> str:
    value = unicodedata.normalize("NFKC", title).strip()
    value = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "-", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"-{2,}", "-", value).strip(" .-")
    if not value:
        value = fallback
    if value.upper() in WINDOWS_RESERVED_NAMES:
        value = f"{value}-note"
    value = value[:max_length].rstrip(" .-")
    return value or fallback


def is_safe_public_url_for_tavily(value: str) -> tuple[bool, str | None]:
    try:
        safe_url = sanitize_url(value)
        parsed = urllib.parse.urlsplit(safe_url.source_url)
    except CaptureError:
        return False, "invalid URL"

    if safe_url.redacted:
        return False, "URL contains credentials or sensitive query parameters"

    host = parsed.hostname.lower().rstrip(".") if parsed.hostname else ""
    if host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
        return False, "local or internal host"

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and not address.is_global:
        return False, "private or non-global IP address"

    return True, None


def _read_optional_file(path_value: str | None) -> str:
    if not path_value:
        return ""
    if path_value == "-":
        return sys.stdin.read().strip()
    return Path(path_value).read_text(encoding="utf-8").strip()


def _yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _yaml_list(name: str, values: Iterable[str]) -> list[str]:
    cleaned = [value.strip() for value in values if value and value.strip()]
    if not cleaned:
        return [f"{name}: []"]
    return [f"{name}:", *[f"  - {_yaml_string(value)}" for value in cleaned]]


def _decode_frontmatter_scalar(raw: str) -> str:
    value = raw.strip()
    if value.startswith('"'):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return ""
        return decoded if isinstance(decoded, str) else str(decoded)
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def _frontmatter_fields(text: str) -> dict[str, str]:
    match = re.match(r"\A---\r?\n(?P<body>.*?)\r?\n---(?:\r?\n|\Z)", text, re.DOTALL)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group("body").splitlines():
        field = re.match(r"^(?P<name>[A-Za-z_][A-Za-z0-9_-]*):\s*(?P<value>.*)$", line)
        if field:
            fields[field.group("name")] = _decode_frontmatter_scalar(field.group("value"))
    return fields


def _iter_markdown_files(vault: Path) -> Iterable[Path]:
    for root, directories, files in os.walk(vault):
        directories[:] = [name for name in directories if name not in SKIP_DIRECTORIES]
        root_path = Path(root)
        for filename in files:
            if filename.lower().endswith(".md"):
                yield root_path / filename


def _read_note_identity(note_path: Path) -> NoteIdentity | None:
    try:
        with note_path.open("r", encoding="utf-8") as handle:
            fields = _frontmatter_fields(handle.read(32768))
    except (OSError, UnicodeError):
        return None
    if fields.get("type") != "source":
        return None
    return NoteIdentity(
        path=note_path,
        source_id=fields.get("source_id", ""),
        source_url=fields.get("source_url", ""),
        canonical_url=fields.get("canonical_url", ""),
        canonicalization_version=fields.get("canonicalization_version", ""),
    )


def _is_proven_legacy(identity: NoteIdentity) -> bool:
    if identity.canonicalization_version == "1":
        return True
    if identity.canonicalization_version or not identity.source_url or not identity.canonical_url:
        return False
    try:
        v1 = _legacy_canonicalize_url(identity.source_url)
        v2 = canonicalize_url(identity.source_url)
    except CaptureError:
        return False
    return identity.canonical_url == v1 and v1 != v2


def find_duplicate(vault: Path, safe_url: SafeUrl, source_id: str) -> Path | None:
    for note_path in _iter_markdown_files(vault):
        identity = _read_note_identity(note_path)
        if not identity:
            continue
        if identity.source_id == source_id or identity.canonical_url == safe_url.canonical_url:
            return note_path
        if not _is_proven_legacy(identity):
            continue
        if identity.canonical_url != safe_url.legacy_canonical_url:
            continue
        if identity.source_id and identity.source_id != source_id_for(identity.canonical_url):
            continue
        return note_path
    return None


@contextmanager
def _identity_claim(vault: Path, source_id: str) -> Iterable[None]:
    lock_directory = vault / IDENTITY_LOCK_DIRECTORY
    lock_directory.mkdir(parents=True, exist_ok=True)
    lock_path = lock_directory / f"{source_id}.lock"
    token = secrets.token_hex(16)
    deadline = time.monotonic() + IDENTITY_LOCK_TIMEOUT_SECONDS

    while True:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "w", encoding="ascii") as handle:
                handle.write(token)
                handle.flush()
                os.fsync(handle.fileno())
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise CaptureError("Another capture for this source is still in progress.")
            time.sleep(IDENTITY_LOCK_POLL_SECONDS)
        except OSError as exc:
            raise CaptureError("Could not create a safe identity lock.") from exc

    try:
        yield
    finally:
        try:
            if lock_path.read_text(encoding="ascii") == token:
                lock_path.unlink()
        except (FileNotFoundError, OSError, UnicodeError):
            pass


def extract_with_tavily(url: str, depth: str, timeout: float = 30.0) -> TavilyResult:
    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        raise TavilyConfigurationError("TAVILY_API_KEY is not set in this plugin process.")

    payload = json.dumps(
        {
            "urls": url,
            "extract_depth": depth,
            "format": "markdown",
            "include_images": False,
            "include_favicon": False,
            "include_usage": True,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.tavily.com/extract",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "web-to-obsidian/0.3.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise CaptureError(f"Tavily extraction failed with HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise CaptureError("Tavily extraction could not connect.") from exc
    except (TimeoutError, json.JSONDecodeError) as exc:
        raise CaptureError("Tavily extraction returned an invalid or timed-out response.") from exc

    results = data.get("results") or []
    if not results:
        raise CaptureError("Tavily could not extract this URL.")

    content = str(results[0].get("raw_content") or "").strip()
    if not content:
        raise CaptureError("Tavily returned no page content.")
    return TavilyResult(content=content, depth=depth, request_id=data.get("request_id"))


_PUBLIC_HTML_MAX_REDIRECTS = 3
_PUBLIC_HTML_MAX_BYTES = 10 * 1024 * 1024
_PUBLIC_HTML_ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml")


def _is_public_html_host_safe(url: str) -> tuple[bool, str | None]:
    """Resolve the host and confirm every resolved address is public.
    is_safe_public_url_for_tavily() only pattern-matches the literal host
    string — it never resolves DNS, so a hostname whose DNS record points
    at a private address, or a numeric-IP shorthand like 127.1, passes it
    unnoticed. This closes that gap for the public-HTML fetch tier only.
    """
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname
    if not host:
        return False, "missing host"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        return False, f"could not resolve host: {exc}"
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            return False, f"resolved address {address} is not public"
    return True, None


class _SafePublicHtmlRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-validate every redirect hop against the same public/private-IP
    check used for the original URL, cap the number of hops, and never
    forward cookies or auth headers across a hop. Without this, a URL that
    is safe at request time could still redirect to a private IP or
    localhost (SSRF via redirect, including DNS rebinding).
    """

    def __init__(self) -> None:
        self.redirect_count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.redirect_count += 1
        if self.redirect_count > _PUBLIC_HTML_MAX_REDIRECTS:
            raise CaptureError("Public HTML fetch exceeded the redirect limit.")
        safe, reason = is_safe_public_url_for_tavily(newurl)
        if not safe:
            raise CaptureError(
                f"Public HTML fetch redirected to an unsafe URL: {reason}."
            )
        host_safe, host_reason = _is_public_html_host_safe(newurl)
        if not host_safe:
            raise CaptureError(
                f"Public HTML fetch redirected to an unsafe URL: {host_reason}."
            )
        new_request = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_request is not None:
            new_request.remove_header("Cookie")
            new_request.remove_header("Authorization")
        return new_request


def fetch_public_html(url: str, timeout: float = 15.0) -> str:
    """Fetch a public URL's raw HTML directly, no browser involved. Callers
    must gate the *original* URL with is_safe_public_url_for_tavily() first;
    this function re-validates every redirect hop on top of that, caps
    redirects and response size, and never forwards cookies or auth headers.
    """

    request = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "web-to-obsidian/0.3.0"},
    )
    opener = urllib.request.build_opener(_SafePublicHtmlRedirectHandler())
    try:
        with opener.open(request, timeout=timeout) as response:
            content_type = (
                response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            )
            if content_type and content_type not in _PUBLIC_HTML_ALLOWED_CONTENT_TYPES:
                raise CaptureError(
                    f"Public HTML fetch got an unsupported content type: {content_type}."
                )
            raw = response.read(_PUBLIC_HTML_MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise CaptureError(f"Public HTML fetch failed with HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise CaptureError("Public HTML fetch could not connect.") from exc
    except TimeoutError as exc:
        raise CaptureError("Public HTML fetch timed out.") from exc

    if len(raw) > _PUBLIC_HTML_MAX_BYTES:
        raise CaptureError("Public HTML fetch exceeded the size limit.")
    text = raw.decode("utf-8", errors="replace")
    if not _looks_like_html_capture(text):
        raise CaptureError("The fetched page did not contain HTML structure.")
    return text


def _within(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _resolve_within(
    root: Path,
    candidate: Path,
    *,
    attempts: int = 3,
) -> Path | None:
    """Resolve a path inside root, tolerating transient Windows filesystem races."""

    for attempt in range(attempts):
        resolved = candidate.resolve()
        if _within(root, resolved):
            return resolved
        if attempt + 1 < attempts:
            time.sleep(0)
    return None


def _normalize_cssclasses(values: Iterable[str]) -> list[str]:
    cssclasses = ["web-clip"]
    for value in values:
        cssclass = value.strip()
        if not CSS_CLASS_PATTERN.fullmatch(cssclass):
            raise CaptureError(
                "CSS class must contain only letters, numbers, hyphens, or underscores."
            )
        if cssclass not in cssclasses:
            cssclasses.append(cssclass)
    return cssclasses


def markdown_destination(url: str) -> str:
    """Protect Markdown syntax while preserving URL reserved characters."""
    if any(char in url for char in '()&'):
        return '<' + url.replace('\\', '\\\\').replace('&', '&amp;') + '>'
    return url


def parse_markdown_destination(destination: str) -> str:
    """Decode angle destinations while preserving legacy raw callouts."""
    if destination.startswith('<') and destination.endswith('>'):
        return html_lib.unescape(destination[1:-1].replace('\\\\', '\\'))
    return destination


def _render_note(
    *,
    title: str,
    content_type: str,
    source_id: str,
    source_url: str,
    canonical_url: str,
    source_url_redacted: bool,
    author: str,
    published: str,
    captured: str,
    capture_method: str,
    platform: str,
    cssclasses: list[str],
    tags: list[str],
    topics: list[str],
    why: str,
    selection: str,
    summary: str,
    content: str,
    rich_html: bool,
    tavily_request_id: str | None,
) -> str:
    lines = [
        "---",
        "type: source",
        f"content_type: {content_type}",
        "status: inbox",
        f"cssclasses: [{', '.join(cssclasses)}]",
        f"source_id: {_yaml_string(source_id)}",
        f"title: {_yaml_string(title)}",
        f"source_url: {_yaml_string(source_url)}",
        f"canonical_url: {_yaml_string(canonical_url)}",
        "canonicalization_version: 2",
        f"source_url_redacted: {'true' if source_url_redacted else 'false'}",
        f"author: {_yaml_string(author)}",
        f"published: {_yaml_string(published)}" if published else "published:",
        f"captured: {_yaml_string(captured)}",
        f"capture_method: {capture_method}",
        f"platform: {_yaml_string(platform)}",
        f"link_only: {'false' if content or selection else 'true'}",
    ]
    if tavily_request_id:
        lines.append(f"tavily_request_id: {_yaml_string(tavily_request_id)}")
    lines.extend(_yaml_list("tags", tags))
    lines.extend(_yaml_list("topics", topics))
    lines.extend(["---", "", f"# {title}", "", "> [!info] Nguồn", f"> [Mở liên kết gốc]({markdown_destination(source_url)})"])

    if why:
        lines.extend(["", "## Vì sao tôi lưu", "", why])
    if selection:
        quoted = "\n".join(f"> {line}" if line else ">" for line in selection.splitlines())
        lines.extend(["", "## Đoạn đã chọn", "", quoted])
    if summary:
        lines.extend(["", "## Tóm tắt", "", summary])
    if content:
        source_lines = ["", SOURCE_CONTENT_START]
        if not rich_html:
            source_lines.extend(["## Nội dung nguồn", ""])
        source_lines.extend([content, SOURCE_CONTENT_END])
        lines.extend(source_lines)
    if not content and not selection:
        lines.extend(["", "> [!warning] Link-only capture", "> Không lấy được nội dung trang tại thời điểm lưu."])
    lines.extend(["", PERSONAL_NOTES_START, "## Ghi chú của tôi", ""])
    return "\n".join(lines).rstrip() + "\n"


def _render_review_note(
    *,
    title: str,
    source_id: str,
    source_url: str,
    canonical_url: str,
    source_url_redacted: bool,
    captured: str,
    capture_method: str,
    review_issues: list[str],
    reported_update_date: str | None,
    content: str,
    tavily_request_id: str | None,
) -> str:
    lines = [
        "---",
        "type: capture-review",
        "status: needs-review",
        f"source_id: {_yaml_string(source_id)}",
        f"title: {_yaml_string(title)}",
        f"source_url: {_yaml_string(source_url)}",
        f"canonical_url: {_yaml_string(canonical_url)}",
        f"source_url_redacted: {'true' if source_url_redacted else 'false'}",
        f"captured: {_yaml_string(captured)}",
        f"capture_method: {capture_method}",
    ]
    if reported_update_date:
        lines.append(f"reported_update_date: {_yaml_string(reported_update_date)}")
    if tavily_request_id:
        lines.append(f"tavily_request_id: {_yaml_string(tavily_request_id)}")
    lines.extend(_yaml_list("review_issues", review_issues))
    lines.extend(
        [
            "---",
            "",
            f"# {title}",
            "",
            "> [!warning] Needs review before use",
            "> This capture failed validation and was not written to the main note.",
        ]
    )
    for issue in review_issues:
        lines.append(f"> - {issue}")
    lines.extend(["", SOURCE_CONTENT_START, content.strip(), SOURCE_CONTENT_END])
    return "\n".join(lines).rstrip() + "\n"


def _write_review_note(
    vault: Path,
    folder: str,
    captured_date: str,
    filename_title: str,
    source_id: str,
    note_text: str,
) -> Path:
    review_folder = _resolve_within(vault, vault / folder / "Needs Review")
    if review_folder is None:
        raise CaptureError("Needs Review folder must stay inside the vault.")
    review_folder.mkdir(parents=True, exist_ok=True)
    for candidate in _destination_candidates(
        review_folder, captured_date, filename_title, source_id
    ):
        resolved_candidate = _resolve_within(vault, candidate)
        if resolved_candidate is None:
            raise CaptureError("Needs Review note must stay inside the vault.")
        try:
            with open(resolved_candidate, "x", encoding="utf-8", newline="\n") as handle:
                handle.write(note_text)
        except FileExistsError:
            continue
        return resolved_candidate
    raise CaptureError("Could not publish a Needs Review note without overwrite risk.")


def _destination_candidates(
    destination_folder: Path,
    captured_date: str,
    filename_title: str,
    source_id: str,
) -> Iterable[Path]:
    yield destination_folder / f"{captured_date} - {filename_title}.md"
    short_id = source_id[:6]
    yield destination_folder / f"{captured_date} - {filename_title} - {short_id}.md"
    index = 2
    while True:
        yield destination_folder / f"{captured_date} - {filename_title} - {short_id}-{index}.md"
        index += 1


def _duplicate_result(
    duplicate: Path,
    *,
    source_id: str,
    canonical_url: str,
    source_url_redacted: bool,
    warnings: list[str],
) -> dict[str, object]:
    return {
        "status": "duplicate",
        "source_id": source_id,
        "canonical_url": canonical_url,
        "source_url_redacted": source_url_redacted,
        "path": str(duplicate.resolve()),
        "warnings": warnings,
    }


def _merge_refreshed_source_content(
    existing_note: str,
    content: str,
    capture_method: str,
    *,
    rich_html: bool = False,
) -> str:
    """Replace only the generated source section and preserve user notes/metadata."""

    personal_markers = [
        match.start()
        for match in re.finditer(
            rf"(?m)^{re.escape(PERSONAL_NOTES_START)}\s*$",
            existing_note,
        )
    ]
    if len(personal_markers) > 1:
        raise CaptureError("The existing note has an ambiguous personal-notes boundary.")
    if personal_markers:
        notes_start = personal_markers[0]
        tail = existing_note[notes_start:]
    else:
        legacy_notes = list(
            re.finditer(r"(?m)^## Ghi chú của tôi\s*$", existing_note)
        )
        if len(legacy_notes) != 1:
            raise CaptureError(
                "The existing note has an ambiguous personal-notes boundary."
            )
        notes_start = legacy_notes[0].start()
        tail = PERSONAL_NOTES_START + "\n" + existing_note[notes_start:]

    source_markers = [
        match.start()
        for match in re.finditer(
            rf"(?m)^{re.escape(SOURCE_CONTENT_START)}\s*$",
            existing_note[:notes_start],
        )
    ]
    if len(source_markers) > 1:
        raise CaptureError("The existing note has an ambiguous source-content boundary.")
    if source_markers:
        source_start = source_markers[0]
    else:
        legacy_sources = list(
            re.finditer(
                r"(?m)^## Nội dung nguồn\s*$",
                existing_note[:notes_start],
            )
        )
        if len(legacy_sources) > 1:
            raise CaptureError(
                "The existing note has an ambiguous source-content boundary."
            )
        source_start = legacy_sources[0].start() if legacy_sources else notes_start

    if notes_start < source_start:
        raise CaptureError(
            "The existing note has invalid generated section boundaries; refresh stopped."
        )
    prefix = existing_note[:source_start]
    if source_start == notes_start:
        prefix = re.sub(
            r"(?m)^> \[!warning\] Link-only capture\r?\n"
            r"> Không lấy được nội dung trang tại thời điểm lưu\.\r?\n?",
            "",
            prefix,
            count=1,
        )

    prefix = re.sub(
        r"(?m)^capture_method:\s*.*$",
        f"capture_method: {capture_method}",
        prefix,
        count=1,
    )
    prefix = re.sub(
        r"(?m)^link_only:\s*.*$",
        "link_only: false",
        prefix,
        count=1,
    )
    heading = "" if rich_html else "## Nội dung nguồn\n\n"
    return (
        prefix.rstrip()
        + f"\n\n{SOURCE_CONTENT_START}\n{heading}"
        + content.strip()
        + f"\n{SOURCE_CONTENT_END}\n\n"
        + tail.lstrip()
    ).rstrip() + "\n"


def _atomic_replace_note(path: Path, text: str) -> None:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.stem}-refresh-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, path)
        temp_path = None
    except OSError as exc:
        raise CaptureError("Could not atomically refresh the existing note.") from exc
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def run_capture(args: argparse.Namespace) -> dict[str, object]:
    vault = Path(args.vault).expanduser().resolve()
    if not vault.is_dir():
        raise CaptureError(f"Vault does not exist or is not a directory: {vault}")

    cssclasses = _normalize_cssclasses(getattr(args, "cssclass", []))
    safe_url = sanitize_url(args.url)
    _validate_social_permalink(
        safe_url.source_url,
        content_type=args.content_type,
        confirmed=bool(getattr(args, "confirm_social_permalink", False)),
    )
    canonical_url = safe_url.canonical_url
    source_id = source_id_for(canonical_url)
    warnings: list[str] = []
    if safe_url.redacted:
        warnings.append("Sensitive URL components were removed before storage.")

    refresh_existing = bool(getattr(args, "refresh_existing", False))
    duplicate = find_duplicate(vault, safe_url, source_id)
    if duplicate and not refresh_existing:
        return _duplicate_result(
            duplicate,
            source_id=source_id,
            canonical_url=canonical_url,
            source_url_redacted=safe_url.redacted,
            warnings=warnings,
        )

    content = _read_optional_file(args.content_file)
    html_content = _read_optional_file(getattr(args, "html_file", None))
    if html_content and not _looks_like_html_capture(html_content):
        raise CaptureError("The HTML file does not contain HTML structure.")
    rich_html = bool(html_content) or _looks_like_html_capture(content)
    if rich_html:
        html_content = html_content or content
        converted = html_to_markdown(
            html_content,
            safe_url.source_url,
            heading_offset=1,
        )
        if not converted:
            raise CaptureError("The HTML capture did not contain usable page content.")
        content = converted
    elif args.capture_method == "chrome" and content:
        if not getattr(args, "allow_text_only", False):
            raise CaptureError(
                "Chrome text capture cannot preserve hyperlinks. Provide raw DOM/HTML in "
                "--content-file or --html-file, "
                "or use --allow-text-only for an explicitly text-only note."
            )
        warnings.append(
            "Browser text was supplied without HTML; hyperlinks and other page "
            "structure may be missing. Use --html-file for a linked article."
        )
    selection = _read_optional_file(args.selection_file)
    had_browser_content = bool(content or selection)

    fetched_public_html = False
    if not had_browser_content and getattr(args, "fetch_public_html", False):
        safe, reason = is_safe_public_url_for_tavily(args.url)
        host_safe, host_reason = (
            _is_public_html_host_safe(safe_url.source_url) if safe else (True, None)
        )
        if not safe:
            warnings.append(f"Public HTML fetch skipped: {reason}.")
        elif not host_safe:
            warnings.append(f"Public HTML fetch skipped: {host_reason}.")
        else:
            try:
                fetched_html = fetch_public_html(safe_url.source_url, timeout=args.timeout)
            except CaptureError as exc:
                warnings.append(f"Public HTML fetch failed: {exc}")
            else:
                converted = html_to_markdown(
                    fetched_html, safe_url.source_url, heading_offset=1
                )
                if converted:
                    content = converted
                    html_content = fetched_html
                    rich_html = True
                    fetched_public_html = True
                else:
                    warnings.append(
                        "Public HTML fetch succeeded but produced no usable content."
                    )

    tavily_request_id: str | None = None
    tavily_depth: str | None = None

    if args.tavily == "auto":
        needs_content = not bool(content or selection)
    else:
        needs_content = args.tavily in {"basic", "advanced"}
    if args.tavily != "off" and needs_content:
        safe, reason = is_safe_public_url_for_tavily(args.url)
        if not safe:
            warnings.append(f"Tavily skipped: {reason}.")
        else:
            depths = [args.tavily] if args.tavily in {"basic", "advanced"} else ["basic", "advanced"]
            last_error: CaptureError | None = None
            for depth in depths:
                try:
                    result = extract_with_tavily(
                        safe_url.source_url, depth, timeout=args.timeout
                    )
                    tavily_request_id = result.request_id
                    if len(result.content) > len(content):
                        content = result.content
                        tavily_depth = result.depth
                        rich_html = False
                    if len(content) >= args.min_content_chars:
                        break
                except TavilyConfigurationError as exc:
                    warnings.append(str(exc))
                    break
                except CaptureError as exc:
                    last_error = exc
            if not tavily_depth and last_error:
                warnings.append("Tavily extraction failed.")

    content = _insert_toc_after_header(content, _generate_toc_from_headings(content))

    capture_method = args.capture_method
    if tavily_depth:
        if args.capture_method in {"chrome", "selection"} and had_browser_content:
            capture_method = "hybrid"
        else:
            capture_method = f"tavily-{tavily_depth}"
    elif fetched_public_html:
        capture_method = "public-html"

    parsed = urllib.parse.urlsplit(canonical_url)
    platform = args.platform.strip() if args.platform else parsed.hostname or ""
    captured = args.captured or datetime.now().astimezone().isoformat(timespec="seconds")
    title = args.title.strip() or platform or source_id
    filename_title = sanitize_filename(title, source_id)
    captured_date = captured[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", captured) else datetime.now().date().isoformat()

    review_issues = (
        _collect_content_review_issues(
            content, source_html=html_content if rich_html else None
        )
        if content
        else []
    )
    reported_update_date = _extract_reported_update_date(content) if content else None
    if review_issues:
        if args.dry_run:
            return {
                "status": "needs-review",
                "source_id": source_id,
                "canonical_url": canonical_url,
                "source_url_redacted": safe_url.redacted,
                "capture_method": capture_method,
                "link_only": not bool(content or selection),
                "review_issues": review_issues,
                "reported_update_date": reported_update_date,
                "path": None,
                "warnings": warnings,
            }
        review_note = _render_review_note(
            title=title,
            source_id=source_id,
            source_url=safe_url.source_url,
            canonical_url=canonical_url,
            source_url_redacted=safe_url.redacted,
            captured=captured,
            capture_method=capture_method,
            review_issues=review_issues,
            reported_update_date=reported_update_date,
            content=content,
            tavily_request_id=tavily_request_id,
        )
        review_path = _write_review_note(
            vault, args.folder, captured_date, filename_title, source_id, review_note
        )
        return {
            "status": "needs-review",
            "source_id": source_id,
            "canonical_url": canonical_url,
            "source_url_redacted": safe_url.redacted,
            "capture_method": capture_method,
            "link_only": not bool(content or selection),
            "review_issues": review_issues,
            "reported_update_date": reported_update_date,
            "path": str(review_path),
            "warnings": warnings,
        }

    destination_folder_candidate = (
        duplicate.parent
        if duplicate and refresh_existing
        else vault / args.folder
    )
    destination_folder = _resolve_within(vault, destination_folder_candidate)
    if destination_folder is None:
        raise CaptureError("Destination folder must stay inside the vault.")

    if duplicate and refresh_existing:
        destination = duplicate.resolve()
    else:
        candidates = _destination_candidates(
            destination_folder, captured_date, filename_title, source_id
        )
        destination = next(candidate for candidate in candidates if not candidate.exists())
    resolved_destination = _resolve_within(vault, destination)
    if resolved_destination is None:
        raise CaptureError("Destination note must stay inside the vault.")
    destination = resolved_destination

    tags = list(dict.fromkeys(["web-capture", f"source/{args.content_type}", *args.tag]))
    topics = list(dict.fromkeys(args.topic))
    note = _render_note(
        title=title,
        content_type=args.content_type,
        source_id=source_id,
        source_url=safe_url.source_url,
        canonical_url=canonical_url,
        source_url_redacted=safe_url.redacted,
        author=args.author.strip(),
        published=args.published.strip(),
        captured=captured,
        capture_method=capture_method,
        platform=platform,
        cssclasses=cssclasses,
        tags=tags,
        topics=topics,
        why=args.why.strip(),
        selection=selection,
        summary=args.summary.strip(),
        content=content,
        rich_html=rich_html,
        tavily_request_id=tavily_request_id,
    )

    if args.dry_run:
        return {
            "status": "dry-run",
            "source_id": source_id,
            "canonical_url": canonical_url,
            "source_url_redacted": safe_url.redacted,
            "capture_method": capture_method,
            "link_only": not bool(content or selection),
            "reported_update_date": reported_update_date,
            "path": str(destination),
            "warnings": warnings,
        }

    destination_folder.mkdir(parents=True, exist_ok=True)
    with _identity_claim(vault, source_id):
        duplicate = find_duplicate(vault, safe_url, source_id)
        if duplicate:
            if refresh_existing:
                if not content:
                    raise CaptureError(
                        "Refreshing an existing note requires captured source content."
                    )
                if not _within(vault, duplicate.resolve()):
                    raise CaptureError("Existing note must stay inside the vault.")
                existing_note = duplicate.read_text(encoding="utf-8")
                refreshed_note = _merge_refreshed_source_content(
                    existing_note,
                    content,
                    capture_method,
                    rich_html=rich_html,
                )
                _atomic_replace_note(duplicate, refreshed_note)
                return {
                    "status": "refreshed",
                    "source_id": source_id,
                    "canonical_url": canonical_url,
                    "source_url_redacted": safe_url.redacted,
                    "capture_method": capture_method,
                    "link_only": False,
                    "reported_update_date": reported_update_date,
                    "path": str(duplicate.resolve()),
                    "warnings": warnings,
                }
            return _duplicate_result(
                duplicate,
                source_id=source_id,
                canonical_url=canonical_url,
                source_url_redacted=safe_url.redacted,
                warnings=warnings,
            )

        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                newline="\n",
                dir=destination_folder,
                prefix=f".{source_id}-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(note)
                handle.flush()
                os.fsync(handle.fileno())
                temp_path = Path(handle.name)
            for candidate in _destination_candidates(
                destination_folder, captured_date, filename_title, source_id
            ):
                resolved_candidate = _resolve_within(vault, candidate)
                if resolved_candidate is None:
                    raise CaptureError("Destination note must stay inside the vault.")
                try:
                    os.link(temp_path, resolved_candidate)
                    destination = resolved_candidate
                    break
                except FileExistsError:
                    duplicate = find_duplicate(vault, safe_url, source_id)
                    if duplicate:
                        return _duplicate_result(
                            duplicate,
                            source_id=source_id,
                            canonical_url=canonical_url,
                            source_url_redacted=safe_url.redacted,
                            warnings=warnings,
                        )
                    continue
                except OSError as exc:
                    raise CaptureError(
                        "This filesystem cannot publish a note without overwrite risk."
                    ) from exc
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink()

    return {
        "status": "created",
        "source_id": source_id,
        "canonical_url": canonical_url,
        "source_url_redacted": safe_url.redacted,
        "capture_method": capture_method,
        "link_only": not bool(content or selection),
        "reported_update_date": reported_update_date,
        "path": str(destination.resolve()),
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vault",
        help=(
            "Vault path; otherwise WEB_TO_OBSIDIAN_VAULT_PATH, "
            "OBSIDIAN_VAULT_PATH, or driftnote.yaml is used"
        ),
    )
    parser.add_argument(
        "--env-file",
        help=(
            "Optional .env path; otherwise loads workspace .env and then the "
            "central .env above the skills directory"
        ),
    )
    parser.add_argument("--url", required=True, help="Original public or browser URL")
    parser.add_argument("--title", default="", help="Source title")
    parser.add_argument("--author", default="", help="Source author or artist")
    parser.add_argument("--published", default="", help="Publication or release date")
    parser.add_argument("--platform", default="", help="Source service; defaults to hostname")
    parser.add_argument("--content-type", choices=CONTENT_TYPES, default="bookmark")
    parser.add_argument(
        "--confirm-social-permalink",
        action="store_true",
        help=(
            "Proceed with an unrecognized Facebook or Instagram URL only after "
            "the user explicitly confirms it is the exact post permalink"
        ),
    )
    parser.add_argument("--capture-method", choices=CAPTURE_METHODS, default="manual")
    parser.add_argument(
        "--content-file",
        help="UTF-8 Markdown, text, or HTML capture; HTML is detected automatically; use - for stdin",
    )
    parser.add_argument(
        "--allow-text-only",
        action="store_true",
        help="Explicitly accept that a Chrome text capture may omit hyperlinks and HTML structure",
    )
    parser.add_argument(
        "--html-file",
        help="UTF-8 browser DOM/HTML file to convert into Obsidian-friendly Markdown",
    )
    parser.add_argument("--selection-file", help="UTF-8 file containing the selected excerpt")
    parser.add_argument("--summary", default="", help="Optional user-approved summary")
    parser.add_argument("--why", default="", help="Why the user saved the source")
    parser.add_argument("--tag", action="append", default=[], help="Additional tag; repeat as needed")
    parser.add_argument("--topic", action="append", default=[], help="Topic; repeat as needed")
    parser.add_argument(
        "--cssclass",
        action="append",
        default=[],
        help="Optional Obsidian CSS class; repeat as needed (web-clip is always included)",
    )
    parser.add_argument("--folder", default="00 Inbox/Web", help="Destination relative to vault root")
    parser.add_argument("--captured", default="", help="ISO timestamp; defaults to local current time")
    parser.add_argument("--tavily", choices=("off", "auto", "basic", "advanced"), default="off")
    parser.add_argument(
        "--fetch-public-html",
        action="store_true",
        help=(
            "When no content or selection is supplied, fetch the public URL's "
            "raw HTML directly (no browser) before falling back to Tavily; "
            "skipped for private, local, or credentialed URLs"
        ),
    )
    parser.add_argument("--min-content-chars", type=int, default=400)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--refresh-existing",
        action="store_true",
        help=(
            "Refresh only the generated source-content section of an exact duplicate; "
            "preserves the existing personal-notes section"
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _configure_utf8_console() -> None:
    """Keep JSON output Unicode-safe on Windows legacy code pages."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    _configure_utf8_console()
    parser = build_parser()
    args = parser.parse_args()
    try:
        workspace = Path.cwd()
        load_dotenv(args.env_file, workspace=workspace)
        args.vault = resolve_vault(args.vault, workspace=workspace)
        result = run_capture(args)
    except (CaptureError, OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
