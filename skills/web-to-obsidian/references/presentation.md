# Progressive presentation / Trình bày tăng tiến

Read this reference only when the user asks for a prettier, gallery, card, wide, dashboard, or multi-column archive. Styling is an optional rendering layer; the captured Markdown, provenance, headings, links, and source sections remain canonical.

## Safety contract / Nguyên tắc an toàn

- Always keep `web-clip`. With no confirmed dependency, stop there and offer the scoped setup from `obsidian-clip-beautifier`.
- Treat themes, CSS snippets, community plugins, Dataview JavaScript, API keys, and edits under `.obsidian` as separate opt-in setup. A capture request alone does not authorize them.
- Add a helper class only when the user requested that presentation and the active theme/snippet supporting it is confirmed. Do not stack alternatives from different systems “just in case.”
- Keep `Source content / Nội dung nguồn` as ordinary Markdown. Multi-column callouts, cards, dashboards, or generated indexes belong in an authored presentation section or separate note.
- Prefer graceful mobile collapse and verify Reading view plus Live Preview. State when a feature is Reading-view-only or plugin-dependent.
- Link to upstream projects and their licenses; do not vendor third-party CSS/theme/plugin code into this skill.

Pass each confirmed class through repeatable `--cssclass`; the helper validates, deduplicates, and keeps `web-clip` first.

## Compatibility matrix / Ma trận tương thích

| Source | Safe reuse in a capture | Dependency and boundary |
|---|---|---|
| [Obsidian CSS Snippets](https://github.com/r-u-s-h-i-k-e-s-h/Obsidian-CSS-Snippets) | Visual inspiration and individually reviewed, scoped snippets | Collection is MIT, but upstream notes that some linked snippets are omitted for licensing. Snippets may break after Obsidian updates; never bulk-copy them. |
| [Minimal](https://github.com/kepano/obsidian-minimal) | `wide`, `img-grid`, `img-wide`, `list-cards`; `cards` for Dataview tables | Require confirmed Minimal-compatible theme. Image grids are Reading-view-only. Card classes do not convert arbitrary prose into cards. See [Minimal helper classes](https://minimal.guide/features/helper-classes). |
| [Cupertino](https://github.com/aaaaalexis/obsidian-cupertino) | Most Minimal helper classes, including width, image-grid, and card families | Require Cupertino. Its support is broad but not a promise that every future Minimal helper remains compatible. |
| [Multi-Column Layout](https://github.com/MaxMiksa/Obsidian-MultiColumn-Layout) | Authored callout layouts for a presentation section | Requires the community plugin and Obsidian 1.5+. It is syntax, not a frontmatter class; never wrap the canonical captured article automatically. |
| [Dashboard Gallery](https://github.com/InlitX/Obsidian-Dashboard-Gallery) | Inspiration for a separate home/index note | Current dashboards depend on Dataview JavaScript and some use QuickAdd or external APIs. Do not turn a routine source note into a dashboard or introduce keys/widgets. |
| [Modular CSS Layout](https://github.com/efemkay/obsidian-modular-css-layout) | `wide-page`, `wide-table`, `wide-callout`; authored multi-column/gallery layouts | Requires its GPL-3.0 snippets. Reference or install upstream only on request; do not copy GPL CSS into this skill’s assets. |

## Choose the smallest profile / Chọn profile nhỏ nhất

| Content need | Confirmed dependency | Classes or action |
|---|---|---|
| Long-form reading | None | `web-clip` only; use the scoped beautifier CSS if the user asks to set it up |
| Wider article or table | Minimal/Cupertino | `wide`, optionally `table-wide` |
| Wider article or table | Modular CSS Layout | `wide-page`, optionally `wide-table` |
| Image-heavy archive | Minimal/Cupertino | `img-grid` plus `img-wide`; disclose Reading-view-only behavior |
| Link or media collection | Minimal/Cupertino | `list-cards`; add cover/aspect helpers only when the note structure actually supports them |
| Two-column comparison | Multi-Column Layout or Modular CSS Layout | Author a separate callout presentation block only after explicit request |
| Vault home/dashboard | Dashboard Gallery | Route to a separate dashboard/setup task; do not alter the captured source note |

If a requested profile is unsupported, save the portable `web-clip` note first and report the missing dependency. Use `obsidian-clip-beautifier` for vault setup, CSS installation, or visual audit; `web-to-obsidian` remains responsible for capture.
