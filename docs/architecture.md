# Architecture

**English** | [Tiếng Việt](architecture.vi.md)

## Design goal

The system should make capture nearly frictionless while keeping source notes traceable and formatting changes conservative. Source preservation, explicit provenance, and no-clobber writes take priority over convenience.

## Components

### ChatGPT browser extension

Provides the current tab, selected text, and signed-in browser context. It is the preferred source for private, authenticated, personalized, local, and paywalled pages.

### `web-to-obsidian`

Routes selection, tab, or URL input into one source note. It applies privacy rules, redacts sensitive URL components before identity is computed, and invokes `save_capture.py` for canonicalization v2, proven-legacy duplicate fallback, identity locking, and atomic no-clobber publication. `audit_sensitive_urls.py` provides an explicit, dry-run-first migration for existing notes.

### Tavily Extract

Fallback for public URLs. Automatic extraction runs only when both browser content and selection are empty; explicit `basic` or `advanced` requests can supplement an incomplete capture. URLs that required redaction never cross this boundary. A successful request ID is recorded even when its content is not selected; `capture_method` changes only when Tavily content is used. Tavily Search is reserved for verification and canonical-source discovery.

### Obsidian inbox

Stores immutable evidence plus user context. `status` drives workflow; folders provide broad ownership boundaries, not a deep topic taxonomy.

### `obsidian-clip-beautifier`

Configures and audits the formatting and presentation layer around captured Markdown: installs scoped CSS, checks Linter rules, prepares polished exports, and stages an inactive experimental Web Clipper template asset. Importing or configuring that template remains optional and requires explicit user intent. The skill operates on captured notes, never captures browser content itself, and never performs semantic rewriting.

The primary supported producer for this layer is the bundled `web-to-obsidian` skill. The official Obsidian Web Clipper template is an experimental compatibility path that creates a smaller, different note schema; it is not currently stable enough to claim equivalent behavior. Shared `web-clip` styling does not provide the capture helper's identity, redaction, duplicate, publication, or refresh guarantees.

### `obsidian-excalidraw-mindmap`

**Status: prototype / demo, under active development — not yet stable.**

Turns one already-captured note into a brainstorm-style Excalidraw diagram: Claude builds a strictly source-derived outline (never inventing ideas), and `generate_excalidraw.py` computes a deterministic radial or tree layout, colors nodes by branch depth, applies Excalidraw's native hand-drawn styling, and publishes the result atomically, no-clobber, both inside the vault (linked from the source note) and optionally as a standalone file. It never captures browser content and never makes content judgments itself — content fidelity stays with the outline Claude provides, and layout/style/publication stay deterministic and testable in the script.

The skill is offered as an optional follow-up right after `web-to-obsidian` finishes a capture, or invoked manually against any already-captured note the user names explicitly. It never guesses which note to diagram.

### Properties, Bases, and MOCs

Properties provide stable machine-readable fields. Bases provide filtered operational views. MOCs remain curated navigation for meaningful themes and projects.

## Identity and deduplication

Canonicalization v2 normalizes the scheme, IDNA host, and default port; removes sensitive and known tracking parameters plus fragments; and preserves trailing slashes and the order of remaining query parameters. The helper hashes that canonical URL with SHA-256; the first 16 hex characters become `source_id`, and new notes record `canonicalization_version: 2`.

Titles are presentation, not identity. A renamed page keeps the same source ID. A meaningfully different query URL keeps a different source ID unless only known tracking parameters differ.

Duplicate lookup checks exact v2 canonical URL/source ID first. It falls back only for notes explicitly marked version 1 or unversioned notes whose stored fields prove v1 canonicalization. Publication holds an exclusive source-ID lock across the duplicate recheck and no-clobber link. A lock timeout fails closed after 10 seconds; stale locks are never deleted or taken over automatically.

## Failure behavior

- Browser capture missing and Tavily disabled: create a link-only note.
- Tavily unavailable or unsuccessful: keep existing browser content; otherwise create a link-only note, and report a value-free warning.
- Existing source ID or canonical URL: return the existing note path and make no write.
- Invalid destination outside the vault: fail before writing.
- Identity lock unavailable for 10 seconds: fail closed and require manual stale-lock recovery.
- Capture publication: fsync a same-directory temporary file, then use an atomic no-clobber hard link; never fall back to overwrite.
- Scanner apply: update only when all structured URLs converge and the note has not changed since it was read; otherwise require manual review.
