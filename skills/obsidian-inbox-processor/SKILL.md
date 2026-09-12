---
name: obsidian-inbox-processor
description: Review source notes captured by web-to-obsidian, preserve their provenance, and turn only durable insights into linked Obsidian knowledge notes. Use for inbox triage, source distillation, atomic-note creation, and status updates. Do not capture browser pages or bulk-generate notes from every source.
---

# Obsidian Inbox Processor

Process captures deliberately. A source can be useful without producing a permanent knowledge note.

## Select work

Resolve the confirmed vault root, then find source notes with `status: inbox`. Default to at most ten notes per run unless the user requests a different scope.

Read [references/processing-rules.md](references/processing-rules.md) before changing notes.

## Triage each source

Choose one outcome:

- **Keep as source:** useful reference, but no durable insight to extract.
- **Create knowledge notes:** one note per durable claim, concept, decision, or reusable method.
- **Needs review:** missing context, conflicting evidence, or a user decision is required.
- **Discard recommendation:** low-value or duplicate capture. Do not delete it without explicit authorization.

Do not create a fixed number of derived notes. Zero is valid.

## Create durable notes

When a source supports a reusable idea:

- State one primary claim per note.
- Write in the user's language unless asked otherwise.
- Link back to the source note with `source_note` and a body wikilink.
- Separate sourced claims from the user's interpretation.
- Mark time-sensitive or uncertain claims for verification.
- Add existing wikilinks only when the relationship is clear; do not generate speculative graph density.
- Update the nearest MOC only when the new note clearly belongs there.

Use `assets/Knowledge Note.md` as a starting shape, omitting empty optional sections.

## Complete processing

After all derived notes are safely written, update the source note:

- Set `status: processed` or `status: needs-review`.
- Add `processed` as an ISO date.
- Add `derived_notes` as quoted wikilinks when any were created.

Never remove raw content during processing. If the Obsidian CLI is available, it may be used for property updates and moves while Obsidian is open. Otherwise edit the Markdown carefully and keep the source in place.

Report created notes, sources marked processed, items needing review, and duplicates. Never claim that a source was verified unless verification actually occurred.
