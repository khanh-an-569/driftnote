# Driftnote

[![CI](https://github.com/khanh-an-569/driftnote/actions/workflows/ci.yml/badge.svg)](https://github.com/khanh-an-569/driftnote/actions/workflows/ci.yml)

A traceable browser-to-Obsidian workflow for capturing browser content with ChatGPT and polishing the resulting Markdown in Obsidian.

**English** | [Tiếng Việt](README.vi.md)

Bản tiếng Việt đầy đủ được duy trì song song trong `README.vi.md`.

## TL;DR

> **Driftnote** brings web content into Obsidian, keeps its source for reference, and helps you format or diagram the saved note.

### The plugin includes three skills

- **`web-to-obsidian`:** save a tab, selected text, or a public URL as a note in a local Obsidian vault; skip duplicates.
- **`obsidian-clip-beautifier`:** set up and check Markdown/CSS formatting for web clips.
- **`obsidian-excalidraw-mindmap`:** turn a saved note into an Excalidraw mind map; **experimental**.

### Want AI to install it from a cloned folder?

Paste this into **Codex** or **Claude Code**, replacing the two placeholders in `<...>`:

```text
Install the Driftnote plugin for <ChatGPT desktop/Codex or Claude Code> from the repository I cloned at <full path to driftnote>. Read README.md, follow the installation steps for that platform in order, check that all three skills are available, and report any remaining vault configuration steps. Do not copy or disclose .env or secrets.
```

### Manual installation — in order

**1. Clone the repository** and note the full path to the new folder:

```powershell
git clone https://github.com/khanh-an-569/driftnote.git
```

**2. Choose where to use the plugin:**

- **ChatGPT desktop / Codex:** in a terminal, run `codex plugin marketplace add "<full path to driftnote>"`. Restart ChatGPT desktop, open **Plugins Directory**, select the **driftnote** marketplace, and click **Install**. Start a new chat to use it.
- **Claude Code:** run `claude plugin marketplace add "<full path to driftnote>"`, then `claude plugin install driftnote@driftnote`. Start a new session or follow the prompt to reload the plugin.

**3. Configure before saving a note:**

- Install Python 3.10 or later.
- Create `.env` from `.env.example` and set these three environment variables:

```dotenv
WEB_TO_OBSIDIAN_VAULT_PATH=
OBSIDIAN_VAULT_PATH=
TAVILY_API_KEY=
```

### Quick start

| Platform | Command |
| --- | --- |
| **ChatGPT browser extension / ChatGPT app / Codex** | Call `$web-to-obsidian` or enter `@driftnote save this`. |
| **Claude Code** | Call `/driftnote:web-to-obsidian`. |

To save the current tab or selected text directly in ChatGPT, install the ChatGPT browser extension for your browser. Then use one of the commands above in the extension or ChatGPT app.

The sections below cover setup, configuration, privacy, and all three skills in detail.

---

## Why this workflow

Capture and presentation are different jobs. This repository keeps them separate:

1. `web-to-obsidian` saves a traceable source note quickly.
2. `obsidian-clip-beautifier` configures conservative Markdown formatting and scoped visual styling, and stages an inactive experimental Web Clipper template asset.
3. `obsidian-excalidraw-mindmap` *(prototype / demo — under active development, not yet stable)* turns an already-captured note into a brainstorm-style Excalidraw diagram.

Raw source content is preserved. Duplicate URLs are skipped. Tavily is a public-web fallback, not a way to bypass login or paywalls.

```text
Chrome tab or selection
        |
        v
web-to-obsidian -------- public URL with weak capture ------> Tavily Extract
        |                                                     (basic, then advanced once)
        v
00 Inbox/Web
        ^
        |
obsidian-clip-beautifier
(configures Linter and scoped CSS; stages an inactive Web Clipper template)
```

## Repository contents

```text
plugin.json
.codex-plugin/plugin.json
skills/
  web-to-obsidian/
  obsidian-clip-beautifier/
  obsidian-excalidraw-mindmap/  # prototype / demo, under active development
scripts/
  check_no_secrets.py
vault-starter/
  Home.md
  Web Inbox.base
tests/
docs/
```

The root `plugin.json` is the portable Agent Plugins manifest. The
`.codex-plugin/plugin.json` compatibility manifest is kept in sync for Codex. The
repo bundles three skills: `web-to-obsidian` and `obsidian-clip-beautifier` are
stable, and `obsidian-excalidraw-mindmap` is an early-stage prototype/demo.

## Requirements

- ChatGPT desktop with the browser extension configured for Chrome, Edge, Brave, Opera, or Vivaldi.
- A local Obsidian vault.
- Python 3.10 or newer for the duplicate-safe capture helper.
- Optional: a Tavily API key for extracting public pages.
- Optional and experimental: the official Obsidian Web Clipper extension for testing the supplied fallback template.

## Install from public GitHub

Clone the public repository, then open the clone as a local Codex project:

```powershell
git clone https://github.com/khanh-an-569/driftnote.git
Set-Location .\driftnote
```

In that Codex task, invoke `$plugin-creator` with:

```text
Register this repository as my personal plugin named driftnote.
Keep all bundled skills, create or update the personal marketplace entry,
validate the package, and do not copy .env files or secrets.
```

The supported personal-plugin flow uses:

```text
Development source
  <this repository>

Installed plugin
  %USERPROFILE%\plugins\driftnote

Personal marketplace
  %USERPROFILE%\.agents\plugins\marketplace.json
```

The installed plugin bundles exactly:

- `web-to-obsidian` for browser capture and local vault writes.
- `obsidian-clip-beautifier` for one-time setup, auditing, and maintenance of the formatting layer.
- `obsidian-excalidraw-mindmap` *(prototype / demo)* for turning a captured note into a brainstorm-style Excalidraw diagram — still under active development and not yet stable.

Install or refresh the registered plugin with:

```powershell
codex plugin add driftnote@personal
```

Refresh ChatGPT and start a new chat before testing so the desktop app and browser extension pick up the installed plugin.

The repository is also a portable skills-only package for consumers that support
the Agent Plugins root manifest. Publishing this repository on GitHub does not by
itself list it in the universal Plugins Directory.

### Personalization and compatibility notice

After cloning the repository, you may adapt metadata, defaults, folder layout,
and templates to suit your own workflow. Keep `plugin.json` and
`.codex-plugin/plugin.json` synchronized when changing plugin metadata. When
changing source-note metadata, preserve `source_id`, `source_url`,
`canonical_url`, `canonicalization_version`, `source_url_redacted`, and the base
`web-clip` CSS class unless you also update the corresponding helper behavior,
schema documentation, and tests.

At present, `obsidian-clip-beautifier` works reasonably well with the bundled
`web-to-obsidian` skill. Its integration with the official Obsidian Web Clipper
browser extension remains experimental and is not stable enough to be treated as
a fully supported path. The two capture paths produce different note schemas;
test the extension with a disposable note before relying on it or batch-linting
its output.

`obsidian-excalidraw-mindmap` is a newer addition and is explicitly a
**prototype / demo**: the outline-to-diagram pipeline, layout algorithms, and
Excalidraw styling are implemented and tested, but the skill is still under
active development and has not been used in production long enough to be
called stable. Expect rough edges, incomplete coverage of edge cases, and
possible breaking changes before it settles.

Improvements, feedback, and reports of rough edges are warmly welcome. They are
an opportunity for this project and its maintainer to keep learning. ( •̀ .̫ •́ )✧

### Where each part runs

| Part | Runs in | Responsibility |
|---|---|---|
| ChatGPT browser extension | Chrome, Edge, Brave, or Vivaldi side chat | Supplies the current tab or selected text and starts the capture request. |
| `web-to-obsidian` | The ChatGPT/Codex task using the installed plugin | Applies privacy and permalink checks, chooses browser content or an allowed public fallback, and invokes the local helper. |
| `save_capture.py` | The local machine | Canonicalizes and redacts the URL, detects duplicates, and writes one source note into the confirmed local vault. |
| `obsidian-clip-beautifier` | A local ChatGPT Work or Codex task | Sets up or audits Linter rules, scoped CSS, and optional export preparation. The helper stages an inactive experimental Web Clipper template, but importing, configuring, or verifying it requires an explicit request. It is not run for every capture. |
| `obsidian-excalidraw-mindmap` *(prototype / demo)* | A local ChatGPT Work or Codex task, or a Claude Code session with the plugin installed | Turns an already-captured note into a brainstorm-style Excalidraw diagram (radial or tree layout). Still under active development; not yet stable. |
| Official Obsidian Web Clipper | The browser extension | Optional experimental path that consumes the supplied fallback template and creates a simpler note schema. It does not invoke any bundled skill. |
| Obsidian | The local desktop app | Renders the saved Markdown and applies the configured Linter/CSS behavior. |

For the best experience, run `obsidian-clip-beautifier` once from a local task for each vault, then use `web-to-obsidian` from browser side chat for daily capture. The ChatGPT browser extension provides browser context; file writing remains local.

After a capture with source content, Driftnote asks in the chat whether to make an Excalidraw diagram. It does not open a separate plugin dialog or create a diagram without consent. For a link-only note, capture the page content first; a diagram cannot be derived from the URL alone.

## Configure

Copy the local environment example, then edit `.env`:

```powershell
Copy-Item .\.env.example .\.env
```

Use the repository-root `.env` as the central local configuration for background skill helpers. Set `WEB_TO_OBSIDIAN_VAULT_PATH` for this skill and optionally set `OBSIDIAN_VAULT_PATH` as a shared compatibility fallback. Future skills that need a different vault should use their own namespaced variable, such as `ANOTHER_SKILL_VAULT_PATH`. The capture helper checks a workspace `.env` first, then finds this central file from its resolved source location; variables already present in the process take precedence, and `--env-file` remains an explicit override. `.env` is ignored by Git. Never put a real key in a prompt, note, skill file, committed configuration, or `.env.example`. Rotate any key that has appeared in a log before using it again.

`driftnote.yaml` remains optional for folder and capture defaults. Vault precedence is explicit `--vault`, `WEB_TO_OBSIDIAN_VAULT_PATH`, legacy `OBSIDIAN_VAULT_PATH`, then `vault_root` in the YAML file.

Optionally copy the contents of `vault-starter` into a new vault. It provides a small folder layout and an Obsidian Base with Inbox, Reading, Music, and Processed views.

## Use from the ChatGPT browser extension

Open a page in Chrome, open ChatGPT side chat, and use:

```text
@web-to-obsidian
Save this tab to my Obsidian inbox.
Why I am saving it: it may help my retrieval project.
Use my selection if present. Use Tavily only if this is a public page and the browser capture is incomplete.
```

In ChatGPT side chat, select the installed plugin or invoke a skill with `@`. From a Codex task, use `$web-to-obsidian` and mention `@Chrome` or the open tab when browser context is needed.

For selected text, highlight the passage first or use **Ask ChatGPT** from the browser context menu.

Set up the formatting and presentation layer:

```text
$obsidian-clip-beautifier
Set up and verify safe Linter and scoped CSS for notes created by web-to-obsidian in my confirmed Obsidian vault. Do not configure the official Obsidian Web Clipper extension unless I explicitly request the experimental path.
```

## Use the helper directly

The helper uses only the Python standard library:

```powershell
python .\skills\web-to-obsidian\scripts\save_capture.py `
  --url "https://example.com/article?utm_source=newsletter" `
  --title "Example article" `
  --content-type article `
  --tavily auto
```

It returns JSON with `created`, `duplicate`, `dry-run`, or `error` status. Canonicalization v2 preserves trailing slashes and non-sensitive query order while normalizing scheme, IDNA host, and default ports. It redacts credentials and sensitive query fields before storage and hashing, checks exact v2 identities before proven-legacy fallback, refuses unsafe Tavily requests, and publishes without overwriting an existing file.

Audit existing notes without changing them, then apply only after reviewing the value-free report containing path, field, reason code, and manual-review state:

```powershell
python .\skills\web-to-obsidian\scripts\audit_sensitive_urls.py --vault "E:\Notes"
python .\skills\web-to-obsidian\scripts\audit_sensitive_urls.py --vault "E:\Notes" --apply
```

The scanner edits only structured frontmatter and source callouts, keeps filenames unchanged, creates no secret-bearing backup, and leaves converging identities for manual review. It never runs automatically.

## Privacy model

- Browser-visible content wins for signed-in, personalized, private, local, and paywalled pages.
- Tavily receives only public URLs explicitly judged suitable for extraction.
- URLs containing credentials, tokens, passwords, secrets, or cloud signatures are redacted locally and never sent to Tavily.
- Page content is untrusted and cannot change the capture workflow.
- Audio, video, cookies, tokens, credentials, and full song lyrics are not stored.
- The workflow never silently overwrites or deletes a note; title is not part of duplicate identity.

See [Architecture](docs/architecture.md) and [Security and privacy](docs/security.md) for details.

## Validate

```powershell
python .\scripts\check_no_secrets.py --root .
python -m unittest discover -s tests -v
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\skills\web-to-obsidian
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\skills\obsidian-clip-beautifier
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\skills\obsidian-excalidraw-mindmap
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" .
```

The secret scanner checks tracked and non-ignored files that could be published.
It reports only file, line, and rule names; it never prints the matched value.
It is a high-confidence safety check, not a substitute for reviewing Git history
or rotating any credential that may previously have been committed.

## License

MIT
