# Contributing

**English** | [Tiếng Việt](CONTRIBUTING.vi.md)

Bản tiếng Việt đầy đủ được duy trì song song trong `CONTRIBUTING.vi.md`.

Keep capture and distillation separate. Changes should preserve source provenance, avoid hidden external writes, and keep Tavily optional and limited to public URLs.

## Development

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Before committing any file — not only before opening a pull request:

1. Run `python scripts/check_no_secrets.py --root .` and fix every reported line first. This applies to every file, including AI-authored planning/audit docs under `docs/superpowers/` and `docs/audits/`, which routinely embed the author's real local paths (e.g. `C:\Users\<name>\...`), machine names, or other personal details while being drafted — CI enforces this on every push via the same script and will fail the whole matrix on one leaked path.
2. Do not commit real vault paths, captured private content, or API keys.

Before opening a pull request:

1. Add or update tests for observable behavior.
2. Run the secret scan described in `docs/security.md`.
3. Validate every skill's `SKILL.md` with the Codex skill validator when it is available.
4. Validate `.codex-plugin/plugin.json` with the Codex plugin validator when it is available.
