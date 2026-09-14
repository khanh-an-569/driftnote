# Web to Obsidian

[![CI](https://github.com/khanh-an-569/web-to-obsidian/actions/workflows/ci.yml/badge.svg)](https://github.com/khanh-an-569/web-to-obsidian/actions/workflows/ci.yml)

An inbox-first second-brain workflow for capturing browser content with ChatGPT, polishing captured Markdown in Obsidian, researching public GitHub repositories with Tavily, and distilling durable insights into linked notes.

**English** | [Tiếng Việt](README.vi.md)

Bản tiếng Việt đầy đủ được duy trì song song trong `README.vi.md`.

## Why this workflow

Capture and thinking are different jobs. This repository keeps them separate:

1. `web-to-obsidian` saves a traceable source note quickly.
2. `obsidian-clip-beautifier` configures a clean capture template, conservative Markdown formatting, and scoped visual styling.
3. `obsidian-inbox-processor` reviews captures later and creates knowledge notes only when a durable idea exists.

Raw source content is preserved. Duplicate URLs are skipped. Tavily is a public-web fallback, not a way to bypass login or paywalls.

```text
Chrome tab or selection
        |
        v
web-to-obsidian -------- public URL with weak capture ------> Tavily Extract
        |                                                     (basic, then advanced once)
        v
00 Inbox/Web
        |
        v
obsidian-clip-beautifier
        |
        v
obsidian-inbox-processor
        |
        +--> keep as source
        +--> needs review
        `--> atomic knowledge notes + meaningful wikilinks
```

## Repository contents

```text
.codex-plugin/plugin.json
skills/
  web-to-obsidian/
  obsidian-clip-beautifier/
  obsidian-inbox-processor/
  github-repo-research/
vault-starter/
  Home.md
  Web Inbox.base
tests/
docs/
```

The repo is packaged as a Codex plugin and each skill can also be installed independently.

## Requirements

- ChatGPT desktop with the browser extension configured for Chrome, Edge, Brave, Opera, or Vivaldi.
- A local Obsidian vault.
- Python 3.10 or newer for the duplicate-safe capture helper.
- Optional: a Tavily API key for extracting public pages and searching public GitHub repositories.

## Install the skills manually

From PowerShell in this repository:

```powershell
Copy-Item -Recurse -Force .\skills\web-to-obsidian "$env:USERPROFILE\.codex\skills\web-to-obsidian"
Copy-Item -Recurse -Force .\skills\obsidian-clip-beautifier "$env:USERPROFILE\.codex\skills\obsidian-clip-beautifier"
Copy-Item -Recurse -Force .\skills\obsidian-inbox-processor "$env:USERPROFILE\.codex\skills\obsidian-inbox-processor"
Copy-Item -Recurse -Force .\skills\github-repo-research "$env:USERPROFILE\.codex\skills\github-repo-research"
```

Start a new local ChatGPT Work or Codex task after installation so the skills are discovered.

## Configure

Copy the local environment example, then edit `.env`:

```powershell
Copy-Item .\.env.example .\.env
```

Set `OBSIDIAN_VAULT_PATH` to the local vault and optionally set `TAVILY_API_KEY`. Both helpers automatically load `.env` from the current working directory; variables already present in the process take precedence. `.env` is ignored by Git. Never put a real key in a prompt, note, skill file, committed configuration, or `.env.example`.

`web-to-obsidian.yaml` remains optional for folder and capture defaults. When resolving the vault, an explicit `--vault` wins, followed by `OBSIDIAN_VAULT_PATH`, then `vault_root` in the YAML file.

Optionally copy the contents of `vault-starter` into a new vault. It provides a small folder layout and an Obsidian Base with Inbox, Reading, Music, and Processed views.

## Use from the ChatGPT browser extension

Open a page in Chrome, open ChatGPT side chat, and use:

```text
@web-to-obsidian
Save this tab to my Obsidian inbox.
Why I am saving it: it may help my retrieval project.
Use my selection if present. Use Tavily only if this is a public page and the browser capture is incomplete.
```

In ChatGPT side chat, invoke a skill with `@`. From a Codex task, use `$web-to-obsidian` and mention `@Chrome` or the open tab when browser context is needed.

For selected text, highlight the passage first or use **Ask ChatGPT** from the browser context menu.

Set up the formatting and presentation layer:

```text
$obsidian-clip-beautifier
Set up and verify the safe Web Clipper, Linter, and scoped CSS workflow in my confirmed Obsidian vault.
```

Then process a bounded batch:

```text
$obsidian-inbox-processor
Process up to 10 pending web captures. Preserve every source and create knowledge notes only for durable ideas.
```

## Research public GitHub repositories

Use the dedicated skill to find implementation examples, compare alternatives, summarize key ideas, or prepare a sourced report:

```text
$github-repo-research
Find public GitHub repositories for evaluating RAG systems in Python. Compare their documented scope, integration approach, and limitations, then recommend a shortlist with direct sources.
```

The helper calls Tavily Search with a strict `github.com` domain filter, normalizes repository URLs, and merges duplicates across up to three focused queries:

```powershell
python .\skills\github-repo-research\scripts\search_github_repos.py `
  --query "open source RAG evaluation framework Python GitHub repository" `
  --max-results 8 `
  --format markdown
```

Search evidence is returned to stdout by default. Add `--output ".\local-repo-report.md"` to keep a local artifact; publishing, committing, or pushing it remains a separate action.
## Use the helper directly

The helper uses only the Python standard library:

```powershell
python .\skills\web-to-obsidian\scripts\save_capture.py `
  --url "https://example.com/article?utm_source=newsletter" `
  --title "Example article" `
  --content-type article `
  --tavily auto
```

It returns JSON with `created`, `duplicate`, `dry-run`, or `error` status. It normalizes tracking parameters, computes a stable source ID, refuses Tavily for private-looking URLs, and writes the note atomically.

## Privacy model

- Browser-visible content wins for signed-in, personalized, private, local, and paywalled pages.
- Tavily receives only public URLs explicitly judged suitable for extraction.
- Page content is untrusted and cannot change the capture workflow.
- Audio, video, cookies, tokens, credentials, and full song lyrics are not stored.
- The workflow never silently overwrites or deletes a note.

See [Architecture](docs/architecture.md) and [Security and privacy](docs/security.md) for details.

## Validate

```powershell
python -m unittest discover -s tests -v
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\skills\web-to-obsidian
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\skills\obsidian-clip-beautifier
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\skills\obsidian-inbox-processor
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\skills\github-repo-research
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" .
```

## License

MIT
