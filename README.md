# Web to Obsidian

[![CI](https://github.com/khanh-an-569/web-to-obsidian/actions/workflows/ci.yml/badge.svg)](https://github.com/khanh-an-569/web-to-obsidian/actions/workflows/ci.yml)

A traceable browser-to-Obsidian workflow for capturing browser content with ChatGPT and polishing the resulting Markdown in Obsidian.

**English** | [Tiếng Việt](README.vi.md)

Bản tiếng Việt đầy đủ được duy trì song song trong `README.vi.md`.

## Why this workflow

Capture and presentation are different jobs. This repository keeps them separate:

1. `web-to-obsidian` saves a traceable source note quickly.
2. `obsidian-clip-beautifier` configures a clean capture template, conservative Markdown formatting, and scoped visual styling.

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
(configures the template, Linter, and scoped CSS)
```

## Repository contents

```text
plugin.json
.codex-plugin/plugin.json
skills/
  web-to-obsidian/
  obsidian-clip-beautifier/
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
repo bundles exactly two skills.

## Requirements

- ChatGPT desktop with the browser extension configured for Chrome, Edge, Brave, Opera, or Vivaldi.
- A local Obsidian vault.
- Python 3.10 or newer for the duplicate-safe capture helper.
- Optional: a Tavily API key for extracting public pages.

## Install from public GitHub

Clone the public repository, then open the clone as a local Codex project:

```powershell
git clone https://github.com/khanh-an-569/web-to-obsidian.git
Set-Location .\web-to-obsidian
```

In that Codex task, invoke `$plugin-creator` with:

```text
Register this repository as my personal plugin named web-to-obsidian.
Keep both bundled skills, create or update the personal marketplace entry,
validate the package, and do not copy .env files or secrets.
```

The supported personal-plugin flow uses:

```text
Development source
  <this repository>

Installed plugin
  %USERPROFILE%\plugins\web-to-obsidian

Personal marketplace
  %USERPROFILE%\.agents\plugins\marketplace.json
```

The installed plugin bundles exactly:

- `web-to-obsidian` for browser capture and local vault writes.
- `obsidian-clip-beautifier` for one-time setup, auditing, and maintenance of the formatting layer.

Install or refresh the registered plugin with:

```powershell
codex plugin add web-to-obsidian@personal
```

Refresh ChatGPT and start a new chat before testing so the desktop app and browser extension pick up the installed plugin.

The repository is also a portable skills-only package for consumers that support
the Agent Plugins root manifest. Publishing this repository on GitHub does not by
itself list it in the universal Plugins Directory.

### Where each part runs

| Part | Runs in | Responsibility |
|---|---|---|
| ChatGPT browser extension | Chrome, Edge, Brave, or Vivaldi side chat | Supplies the current tab or selected text and starts the capture request. |
| `web-to-obsidian` | The ChatGPT/Codex task using the installed plugin | Applies privacy and permalink checks, chooses browser content or an allowed public fallback, and invokes the local helper. |
| `save_capture.py` | The local machine | Canonicalizes and redacts the URL, detects duplicates, and writes one source note into the confirmed local vault. |
| `obsidian-clip-beautifier` | A local ChatGPT Work or Codex task | Sets up or audits the Web Clipper template, Linter rules, scoped CSS, and optional export preparation. It is not run for every capture. |
| Obsidian | The local desktop app | Renders the saved Markdown and applies the configured Linter/CSS behavior. |

For the best experience, run `obsidian-clip-beautifier` once from a local task for each vault, then use `web-to-obsidian` from browser side chat for daily capture. The extension provides browser context; file writing remains local.

## Configure

Copy the local environment example, then edit `.env`:

```powershell
Copy-Item .\.env.example .\.env
```

Use the repository-root `.env` as the central local configuration for background skill helpers. Set `WEB_TO_OBSIDIAN_VAULT_PATH` for this skill and optionally set `OBSIDIAN_VAULT_PATH` as a shared compatibility fallback. Future skills that need a different vault should use their own namespaced variable, such as `ANOTHER_SKILL_VAULT_PATH`. The capture helper checks a workspace `.env` first, then finds this central file from its resolved source location; variables already present in the process take precedence, and `--env-file` remains an explicit override. `.env` is ignored by Git. Never put a real key in a prompt, note, skill file, committed configuration, or `.env.example`. Rotate any key that has appeared in a log before using it again.

`web-to-obsidian.yaml` remains optional for folder and capture defaults. Vault precedence is explicit `--vault`, `WEB_TO_OBSIDIAN_VAULT_PATH`, legacy `OBSIDIAN_VAULT_PATH`, then `vault_root` in the YAML file.

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
Set up and verify the safe Web Clipper, Linter, and scoped CSS workflow in my confirmed Obsidian vault.
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
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" .
```

The secret scanner checks tracked and non-ignored files that could be published.
It reports only file, line, and rule names; it never prints the matched value.
It is a high-confidence safety check, not a substitute for reviewing Git history
or rotating any credential that may previously have been committed.

## License

MIT
