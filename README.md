# Web to Obsidian

[![CI](https://github.com/khanh-an-569/web-to-obsidian/actions/workflows/ci.yml/badge.svg)](https://github.com/khanh-an-569/web-to-obsidian/actions/workflows/ci.yml)

An inbox-first second-brain workflow for capturing browser content with ChatGPT, enriching public pages with Tavily when needed, and distilling only durable insights into Obsidian notes.

[Đọc bằng tiếng Việt](README.vi.md)

## Why this workflow

Capture and thinking are different jobs. This repository keeps them separate:

1. `web-to-obsidian` saves a traceable source note quickly.
2. `obsidian-inbox-processor` reviews captures later and creates knowledge notes only when a durable idea exists.

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
  obsidian-inbox-processor/
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
- Optional: a Tavily API key for extracting public pages.

## Install the skills manually

From PowerShell in this repository:

```powershell
Copy-Item -Recurse -Force .\skills\web-to-obsidian "$env:USERPROFILE\.codex\skills\web-to-obsidian"
Copy-Item -Recurse -Force .\skills\obsidian-inbox-processor "$env:USERPROFILE\.codex\skills\obsidian-inbox-processor"
```

Start a new local ChatGPT Work or Codex task after installation so the skills are discovered.

## Configure

Copy the example configuration and set your real vault path:

```powershell
Copy-Item .\web-to-obsidian.example.yaml .\web-to-obsidian.yaml
```

The real configuration is ignored by Git. To enable Tavily for public pages, expose the key to the local ChatGPT/Codex process as `TAVILY_API_KEY`. Never put the key in a prompt, note, skill file, or committed configuration.

Optionally copy the contents of `vault-starter` into a new vault. It provides a small folder layout and an Obsidian Base with Inbox, Reading, Music, and Processed views.

## Use from the ChatGPT browser extension

Open a page in Chrome, open ChatGPT side chat, and use:

```text
$web-to-obsidian
Save this tab to my Obsidian inbox.
Why I am saving it: it may help my retrieval project.
Use my selection if present. Use Tavily only if this is a public page and the browser capture is incomplete.
```

For selected text, highlight the passage first or use **Ask ChatGPT** from the browser context menu.

Later, process a bounded batch:

```text
$obsidian-inbox-processor
Process up to 10 pending web captures. Preserve every source and create knowledge notes only for durable ideas.
```

## Use the helper directly

The helper uses only the Python standard library:

```powershell
python .\skills\web-to-obsidian\scripts\save_capture.py `
  --vault "D:\Notes\Second Brain" `
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

See [Security](docs/security.md) for the full boundary.

## Validate

```powershell
python -m unittest discover -s tests -v
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\skills\web-to-obsidian
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\skills\obsidian-inbox-processor
python "$env:USERPROFILE\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" .
```

## License

MIT
