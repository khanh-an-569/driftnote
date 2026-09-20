# Design: `obsidian-excalidraw-mindmap` skill

Date: 2026-09-21
Status: Approved (pending spec review)

## Summary

Add a new, additive skill that turns a single captured Obsidian note into a
polished, brainstorm-style Excalidraw mind map: a radial or hierarchical-tree
diagram, colored by branch depth, in Excalidraw's native hand-drawn style,
published both inside the vault (linked from the source note) and optionally
as a standalone `.excalidraw` file. The skill is offered as an optional
follow-up step right after `web-to-obsidian` finishes a capture, and can also
be invoked manually against any existing captured note.

This is a new capability, not a change to existing capture behavior. It does
not modify URL validation, redaction, identity, duplicate handling, or the
Markdown/frontmatter contract owned by `skills/web-to-obsidian/`.

## Goals

- Produce diagrams that are pretty (consistent, non-overlapping layout;
  depth-based color; Excalidraw hand-drawn styling) and faithful to the
  source note's ideas (no invented content, no lossy one-line summarization
  of rich content).
- Support genuine brainstorm-style branching: long content can be split into
  further child nodes rather than being flattened into a single label.
- Fit the repository's existing multi-runtime convention (Codex, ChatGPT,
  Claude) and its safety/atomicity discipline (no-clobber writes, explicit
  regeneration, no silent overwrites).
- Stay strictly additive: never alter `web-to-obsidian`'s core capture
  invariants, never touch the user's `Ghi chú của tôi` section or existing
  frontmatter.

## Non-goals

- Not a general-purpose diagramming tool for arbitrary files (code, PDFs,
  etc.) in this iteration — input is always an already-captured Obsidian
  note.
- Not a replacement for the Obsidian Excalidraw community plugin's own file
  format quirks (`.excalidraw.md` compatibility mode) — output is plain
  `.excalidraw` JSON, which both the plugin and excalidraw.com accept.
- Not an automatic/silent diagram generator — always requires the user to
  opt in, either right after capture or via an explicit manual request.

## Architecture

### New skill layout

```
skills/obsidian-excalidraw-mindmap/
  SKILL.md                     # activation, contract, safety rules
  scripts/
    generate_excalidraw.py     # outline JSON -> layout -> .excalidraw file
  references/
    outline-schema.md          # documents the intermediate outline contract
  agents/
    openai.yaml                # Codex/ChatGPT presentation metadata
```

Follows the same shape as the two existing skills (`web-to-obsidian`,
`obsidian-clip-beautifier`), so it needs no special-casing in the portable
manifest structure beyond being listed alongside them.

### Division of responsibility

- **Claude** reads the source note, builds an *outline* (see schema below)
  strictly from the note's existing heading/bullet structure, and decides —
  per the single run-wide `long_content_strategy` — how to handle content
  that doesn't fit cleanly as a short node label. Claude never invents ideas
  that aren't in the note (mirrors invariant #2 of the parent project).
- **`generate_excalidraw.py`** is a pure, deterministic, testable transform:
  outline JSON in, valid `.excalidraw` JSON out. It owns layout geometry,
  collision avoidance, color-by-depth, hand-drawn styling, and file I/O
  (atomic, no-clobber). It performs no summarization and makes no content
  judgments.

This split keeps content fidelity in the hands of the LLM (its strength) and
visual consistency/testability in the hands of deterministic code (its
strength), and matches the project's existing pattern where
`save_capture.py` owns deterministic I/O while the skill instructions own
judgment calls.

## Input resolution

The skill never guesses which note to use. It resolves input one of two
ways:

1. **Post-capture flow (primary):** immediately after `web-to-obsidian`
   writes a note, the path is already known from that step and is passed
   directly — no search, no "most recent file" heuristic.
2. **Manual flow:** the user names the note explicitly (filename or title)
   in chat. Claude resolves the vault path via the user's
   `web-to-obsidian.yaml`/`.env` configuration, exactly as the capture skill
   does, and reads that file.

## Outline JSON schema (Claude → script contract)

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
  (single-direction hierarchical layout). Chosen by the user at invocation
  time; the skill does not pick a layout on the note's behalf.
- `long_content_strategy`: chosen once per run, applied consistently across
  the whole diagram — no mixing strategies within one generation:
  - `"link"` — node keeps a short topic label only; the script attaches an
    Excalidraw `link` (pointing at `source_note_path#source_anchor`) so the
    full content stays in the note, one click away.
  - `"condense"` — Claude may **split** a long block into multiple child
    nodes (further branching), recursively, until each leaf is short enough
    to render cleanly. This is not a lossy one-line summary: it is
    brainstorm-style decomposition of the same content into more, smaller
    nodes. The script's max-depth limit (below) is the backstop; if a branch
    would need to go deeper than that limit and still isn't short, it falls
    back to `"link"` for that node instead of forcing an oversized box.
  - `"manual"` — node holds a short placeholder and a visually distinct
    (dotted, muted) style, signaling the user is expected to fill it in
    later directly in Excalidraw.
- `action` is per-node (`"full" | "condensed" | "link" | "manual"`); the
  run-wide `long_content_strategy` determines which non-`"full"` action gets
  used when a node needs one.
- `source_anchor` is required whenever `action != "full"`.
- `children` is recursive and arbitrarily nestable — this is what allows
  further branching, not just summarization.

The script validates: unique `id`s, per-action text length limits,
`source_anchor` presence where required, and a maximum tree depth (default
5, counting the root node's direct children as depth 1) to keep both
layouts readable. Validation failures are reported back to Claude to fix the
outline (e.g., split further, or fall back to `link`) — the script never
silently truncates or reinterprets content.

## Layout and styling (in the script)

- **Radial**: root at the diagram center; each node's children split the
  angular space around it proportionally to their subtree's leaf count (so
  large branches don't crowd small ones); ring radius grows per depth level,
  widening automatically if a ring gets crowded.
- **Tree**: single-direction layered layout (root at one end, depth = column
  or row); sibling spacing scaled by subtree leaf count to avoid overlap.
- Both are pure functions of the outline (deterministic, unit-testable for
  "no overlapping bounding boxes" and stable output given a fixed style
  seed).
- Every node renders as a native Excalidraw rectangle + bound text + parent→
  child arrow using real `startBinding`/`endBinding` (so moving a node in
  Excalidraw keeps arrows attached). Styling: `roughness: 2`, Virgil
  (hand-drawn) font, `fillStyle: "hachure"`.
- Color cycles by depth from a fixed palette (contrast-checked
  background/stroke pairs).
- `"link"` nodes: dashed stroke, `link` field set to an Obsidian URI or
  relative path + anchor.
- `"manual"` nodes: dotted stroke, muted color, placeholder text.
- Node boxes auto-size to (wrapped) text within min/max bounds so no box can
  dominate or break the layout.

## Publishing

- Canonical output format is plain `.excalidraw` JSON (not the Obsidian
  plugin's `.excalidraw.md` compatibility wrapper), so the same file works
  both embedded in the vault and dropped directly into excalidraw.com.
- Default location: same folder as the source note, named
  `<note-name>.excalidraw`. Overridable via an optional, purely additive
  `excalidraw_output_dir` key in `web-to-obsidian.yaml`, interpreted as a
  path relative to the vault root (consistent with how the existing config
  resolves note-destination paths) — unset by default, no impact on
  existing configuration.
- Optional standalone export: an additional copy can be written to a
  user-specified directory outside the vault, without touching vault state.
- Writes are atomic (temp file + rename) and no-clobber by default, matching
  `save_capture.py`'s discipline. Overwriting an existing diagram for the
  same note requires an explicit `--regenerate` flag.
- After a successful (or regenerated) write, the skill appends — never
  rewrites — a small section to the end of the source note:
  ```
  ## Sơ đồ Excalidraw
  ![[<note-name>.excalidraw]]
  ```
  This insertion is idempotent (skipped if already present) and never
  touches the note's frontmatter or its `Ghi chú của tôi` section.

## Integration with `web-to-obsidian`

A new, clearly separated section is added at the end of
`skills/web-to-obsidian/SKILL.md`'s workflow description: after a note is
successfully saved, offer the user the option to generate a brainstorm
diagram (asking for `layout` and `long_content_strategy` if they accept),
and if accepted, invoke `obsidian-excalidraw-mindmap` with the just-written
note path. This does not alter any existing validation, redaction,
canonicalization, or duplicate-handling step, and remains fully optional.

## Multi-runtime scope

The new skill follows the existing dual-runtime convention used by
`web-to-obsidian` and `obsidian-clip-beautifier`:

- `SKILL.md` is the portable, runtime-agnostic contract.
- `agents/openai.yaml` provides Codex/ChatGPT presentation metadata.
- Script logic lives under `skills/obsidian-excalidraw-mindmap/scripts/`
  (shared, not Claude-only), consistent with the project's rule that shared
  implementation stays under `skills/`, not under `.claude-plugin/`.
- The relevant manifests (`plugin.json`, `.codex-plugin/plugin.json`,
  `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`) are
  updated together to list the new skill, per the project's instruction to
  review all applicable manifests deliberately rather than copying fields
  blindly between formats.

## Testing plan

- Regression tests added under `tests/` (matching the existing
  `unittest`-based layout) before implementation, per the parent project's
  "add a regression test before changing implementation code" workflow:
  - Outline validation: unique IDs, required `source_anchor`, per-action
    length limits, max-depth enforcement and the `condense`→`link` fallback.
  - Radial and tree layout: no overlapping bounding boxes across a range of
    branch counts/depths; stable output for a fixed style seed.
  - `.excalidraw` output: valid JSON, valid element/binding structure
    (arrows correctly bound to parent/child rectangle IDs), depth-based
    color assignment, correct style flags for `link`/`manual` nodes.
  - File I/O: atomic write, no-clobber without `--regenerate`, idempotent
    note-section append (no duplication on regenerate).
- Existing repository checks (`python -m unittest discover -s tests -q`,
  `python scripts/check_no_secrets.py --root .`,
  `python -m compileall -q skills scripts tests`, `git diff --check`, and
  `claude plugin validate . --strict` if `.claude-plugin/` is present) must
  continue to pass unchanged.

## Open follow-ups (not blocking this spec)

- Exact Obsidian URI scheme/format for the `link` field's deep link should
  be confirmed against the user's Obsidian version during implementation.
- Color palette values and font-size/box-size constants should be pinned to
  concrete numbers during implementation (kept out of this spec to avoid
  premature bikeshedding).
