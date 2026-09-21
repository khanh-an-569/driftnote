# Design: auto-generated TOC fallback for captured notes

Date: 2026-09-21
Status: Approved

## Summary

`save_capture.py` already clones a page's own structured table of contents
(`nav#TOC` / `nav[role="doc-toc"]`) into a collapsed `[!toc]-` callout when
one exists in captured HTML. Most captured pages do not expose such an
element, so most notes get no TOC at all — including notes captured via
`--content-file` (plain Markdown/text), which never go through the
HTML-specific clone logic in the first place.

Add a fallback: when a note's final content has no TOC and enough headings
to make one useful, synthesize a `[!toc]-` callout directly from the
content's own Markdown headings, in the same format as the existing
clone feature.

## Goals

- Give notes captured via `--content-file`, `--html-file` without a native
  page TOC, and Tavily extraction all the same navigable-TOC benefit that
  pages with a native TOC already get.
- Reuse the existing TOC callout format and wikilink style exactly, so the
  reader can't tell whether a TOC was cloned or generated.
- Never invent content: the generated TOC is a mechanical restructuring of
  headings that are already, verbatim, in the note — not a summary, not
  new information.

## Non-goals

- Not a change to the native TOC-clone behavior — it keeps first priority;
  the fallback only runs when no `[!toc]` is already present in the
  content.
- Not configurable per this iteration (no new CLI flag) — default-on,
  matching the always-on native clone behavior it fills a gap for.

## Design

### Where it runs

`run_capture()` finalizes `content` from exactly one of: `--html-file`
(converted via `html_to_markdown`, which may already have inserted a native
TOC), `--content-file` (used as-is), or Tavily extraction. Once `content`
is finalized (after all three paths converge, before duplicate/identity
work), apply:

```python
content = _insert_toc_after_header(content, _generate_toc_from_headings(content))
```

`_insert_toc_after_header` already exists and is format-agnostic (plain
string insertion); reusing it means the generated TOC lands in the exact
same position a cloned one would (right after a `[!web-header]` callout
when present, otherwise at the very start of the content).

### `_generate_toc_from_headings(content: str) -> str`

- Returns `""` immediately if `content` already contains `"[!toc]"` (native
  TOC already cloned — never double up).
- Scans `content` line by line for Markdown ATX headings (`^#{1,6}\s+.+`),
  skipping any line inside a fenced code block (` ``` `-delimited) so a `#`
  in a code sample is never misread as a heading.
- Returns `""` if fewer than 3 headings are found (a 1–2 heading note does
  not need a TOC).
- Builds a nested bullet list using the same ancestor/depth walk and
  wikilink format as the existing `_render_toc_list` (reusing
  `_escape_wikilink`): a top-level heading becomes `[[#Heading]]`; a nested
  heading becomes `[[#Parent#Child|Child]]`. Nesting follows the headings'
  actual ATX levels (a level-3 heading nests under the nearest preceding
  level-2 heading it follows, etc.), not a fixed depth.
- Wraps the result exactly like the existing callout: `> [!toc]- Table of
  contents` followed by `> `-prefixed list lines.

### Interaction with existing invariants

- Does not touch identity, canonicalization, redaction, or duplicate
  logic — it only transforms the already-finalized `content` string before
  it reaches `_render_note`.
- Does not touch `--refresh-existing`'s preserved-content path, since that
  path replaces only the source-content region with freshly resolved
  `content`, which already passes through this same finalization point.
- Headings inside a fenced code block are never treated as TOC entries,
  matching the spirit of "don't reinterpret source meaning."

## Testing plan

Add regression tests to `tests/test_save_capture.py` covering:

1. A `--content-file` capture with ≥3 headings and no native TOC gets a
   generated `[!toc]-` callout with correctly nested wikilinks.
2. A capture with fewer than 3 headings gets no TOC.
3. A capture whose content already contains `[!toc]` (simulating a native
   clone) is left untouched by the fallback — no duplicate TOC.
4. A `#` inside a fenced code block is not treated as a heading.
