# Architecture

**English** | [Tiếng Việt](architecture.vi.md)

## Design goal

The system should make capture nearly frictionless without allowing automated summaries and tags to become the knowledge base. Source preservation, explicit provenance, and reversible processing take priority over graph size.

## Components

### ChatGPT browser extension

Provides the current tab, selected text, and signed-in browser context. It is the preferred source for private, authenticated, personalized, local, and paywalled pages.

### `web-to-obsidian`

Routes selection, tab, or URL input into one source note. It applies privacy rules, classifies the source, and invokes `save_capture.py` for deterministic URL normalization, duplicate detection, and writing.

### Tavily Extract

Fallback for public URLs whose browser capture is empty or incomplete. The policy is basic extraction first, one advanced retry, then a link-only note. Tavily Search is reserved for verification and canonical-source discovery.

### Obsidian inbox

Stores immutable evidence plus user context. `status` drives workflow; folders provide broad ownership boundaries, not a deep topic taxonomy.

### `obsidian-clip-beautifier`

Configures and audits the formatting and presentation layer around captured Markdown: installs the Web Clipper template and scoped CSS snippet, checks Linter rules, and prepares polished exports. It operates on the inbox between capture and distillation, never captures browser content itself, and never distills sources into knowledge notes.

### `obsidian-inbox-processor`

Performs bounded review. It may keep a source, mark it for review, or create zero or more atomic knowledge notes. It never deletes raw content.

### Properties, Bases, and MOCs

Properties provide stable machine-readable fields. Bases provide filtered operational views. MOCs remain curated navigation for meaningful themes and projects.

## Identity and deduplication

The helper removes common tracking parameters and fragments, sorts remaining query parameters, and hashes the canonical URL with SHA-256. The first 16 hex characters become `source_id`.

Titles are presentation, not identity. A renamed page keeps the same source ID. A meaningfully different query URL keeps a different source ID unless only known tracking parameters differ.

## Failure behavior

- Browser capture missing and Tavily disabled: create a link-only note.
- Tavily unavailable or unsuccessful: create a link-only note and report the warning.
- Existing source ID or canonical URL: return the existing note path and make no write.
- Invalid destination outside the vault: fail before writing.
- Partial file write: use a same-directory temporary file and atomic replace.
