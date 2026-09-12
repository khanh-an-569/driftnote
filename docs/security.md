# Security and privacy

**English** | [Tiếng Việt](security.vi.md)

## Trust boundaries

Web pages, selected text, transcripts, metadata, and extracted Markdown are untrusted input. They may be stored as content, but they cannot authorize navigation, tool use, credential access, downloads, or changes outside the confirmed vault.

## Tavily boundary

Tavily is allowed only for intentionally public HTTP(S) pages. Do not use it for:

- authenticated or personalized pages;
- internal company sites;
- localhost, private IPs, `.local`, or `.internal` hosts;
- private messages, email, dashboards, or account pages;
- URLs containing tokens, credentials, signatures, or sensitive query parameters;
- paywalled content visible only through the user's session.

`TAVILY_API_KEY` must come from the environment. Never place it in a repository, command argument, prompt, note, screenshot, or MCP URL committed to source control.

## Local write boundary

The destination must resolve inside the confirmed vault. The capture helper refuses relative folder traversal. Existing notes are never overwritten solely because their filenames match; duplicate detection uses source identity first.

## Copyright and media

Preserve reasonable excerpts and source attribution. For songs, videos, and podcasts, store metadata, user notes, links, and authorized transcripts or excerpts. Do not download media or reproduce full lyrics.

## Public-repository checklist

Before every release:

1. Search the repository for `tvly-`, tokens, credentials, personal vault paths, cookies, and captured private content.
2. Run tests and both skill validators.
3. Review examples for real personal data.
4. Rotate any key that may have appeared in Git history or screenshots.
