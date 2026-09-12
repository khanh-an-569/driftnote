# Contributing

**English** | [Tiếng Việt](CONTRIBUTING.vi.md)

Bản tiếng Việt đầy đủ được duy trì song song trong `CONTRIBUTING.vi.md`.

Keep capture and distillation separate. Changes should preserve source provenance, avoid hidden external writes, and keep Tavily optional and limited to public URLs.

## Development

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Before opening a pull request:

1. Add or update tests for observable behavior.
2. Run the secret scan described in `docs/security.md`.
3. Validate both `SKILL.md` files with the Codex skill validator when it is available.
4. Validate `.codex-plugin/plugin.json` with the Codex plugin validator when it is available.
5. Do not commit real vault paths, captured private content, or API keys.
