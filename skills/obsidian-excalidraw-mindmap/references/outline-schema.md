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
