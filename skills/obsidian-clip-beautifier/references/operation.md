# Operation and maintenance

Use this reference for daily use, bounded cleanup, batch linting, visual checks, and export preparation.

## Daily lifecycle

1. `web-to-obsidian` creates a source note in `00 Inbox/Web` with `status: inbox`.
2. Opening and saving the note, or switching away from it, lets Linter normalize the Markdown when the matching settings are enabled.
3. Review the source, preserve the original URL and raw captured content, and add personal context separately.
4. Leave `status: inbox` unchanged after formatting; a status change is a separate content-review decision.
5. Keep the source in place and move it only when the user explicitly requests a confirmed destination.

Formatting is not semantic processing. Do not summarize, delete source passages, invent metadata, or mark a note `processed` merely because Linter ran.

This lifecycle describes the primary supported `web-to-obsidian` path. Notes created by the official Obsidian Web Clipper extension use a different, smaller schema and belong to an experimental compatibility path. Inspect one disposable extension-created note before applying cleanup or linting rules to more files; do not assume the capture helper's identity, redaction, duplicate, or refresh guarantees apply to it.

## Batch linting

Before the first batch:

1. Create a vault backup or Git commit.
2. Select two or three representative clips, including one with a table or code block.
3. Run Linter on only those files and inspect the diff.
4. Disable or adjust any rule that changes meaning, frontmatter types, links, code, or deliberate line breaks.
5. Only then use the Linter folder command on a bounded folder such as `00 Inbox/Web`.

Never batch lint the entire vault by default. Avoid running two formatters on the same canonical files because Prettier-style wrapping and Linter rules can fight each other.

## Visual verification

For one `web-clip` note and one ordinary note, compare:

- Reading view
- Live Preview
- narrow and wide panes
- light and dark themes when both are used
- headings, callouts, blockquotes, tables, images, links, inline code, and fenced code

If styling leaks into ordinary notes, confirm the captured note has `cssclasses: web-clip` and that selectors remain scoped beneath `.web-clip`.

## Optional publishing

Use MD Beautify only when the user asks for a polished copy for email, a blog, WeChat, or another rich-text editor:

1. Start from the linted Markdown source.
2. Choose a theme and preview the rendered result.
3. Copy or export the presentation result.
4. Keep the original Markdown note as the source of truth.

Do not silently upload images or content. Image hosting, external publishing, and pasting into another service are separate external actions requiring the user's request.

## Troubleshooting

- **A new clip was not linted:** open it and save or switch away, or run the explicit Linter command.
- **Template import fails:** parse the JSON, confirm `schemaVersion`, `name`, `behavior`, `noteContentFormat`, `properties`, `noteNameFormat`, and `path`, then compare against a template exported by the installed Web Clipper version.
- **CSS has no effect:** reload snippets, enable the snippet, and confirm `cssclasses` includes `web-clip`.
- **Formatting changes YAML types:** disable the responsible YAML rule and restore from the checkpoint before retrying.
- **Two formatters keep changing the same lines:** choose Linter for canonical vault Markdown and reserve MD Beautify for presentation output.
