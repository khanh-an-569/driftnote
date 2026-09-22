# Project Health Audit Framework

Maintainer-only, on-demand health check for the driftnote **repository**
itself — not a feature of the driftnote plugin, and never shipped to end
users who install driftnote from a marketplace. Trigger by asking Claude
directly, e.g. "chạy audit theo docs/project-audit-framework.md".

## When to run

On request only. No schedule, no CI hook. Independent of any single
diff/PR — this checks the whole repository as it stands right now, not a
changeset. For reviewing a specific PR/diff, use the `/code-review` skill
instead; this framework is for whole-repo health checks.

## Phase 0 — Snapshot

Record, verbatim, at the top of the new report:

- `git rev-parse HEAD` and `git branch --show-current`
- `git status --porcelain` (or "clean" if empty)
- The current skill list: `find skills -iname SKILL.md` (or equivalent)
- Full pass/fail count from `python -m unittest discover -s tests`

## Phase 1 — Four axes

Work through each axis below. **Every finding must cite `file:line` or a
command plus its literal output.** Do not report a speculative finding.

### 1. Docs ↔ code

Check that each of these documented behaviors matches the code exactly:

- `SKILL.md` workflow steps 1-8 vs. `save_capture.py`'s `resolve_vault()`
  and `run_capture()`, and step 8's Excalidraw-consent instruction vs. the
  actual chat behavior it describes.
- `skills/web-to-obsidian/references/browser-capture.md`'s "HTML
  conversion boundary" section vs. `html_to_markdown()` /
  `_HtmlMarkdownRenderer`.
- `skills/web-to-obsidian/references/note-schema.md`'s `--content-file` /
  `--html-file` semantics vs. `_looks_like_html_capture()` and
  `run_capture()`'s branching around it.
- `skills/web-to-obsidian/references/tavily.md`'s connected-Extract-tool
  paragraph and `--tavily auto` claim vs. `extract_with_tavily()` and
  `TavilyConfigurationError`.
- `README.md`'s Excalidraw-consent paragraph vs. `SKILL.md` step 8 (must
  describe the same conversational-question behavior, not a plugin dialog).

### 2. Bảo mật & quyền truy cập

- `sanitize_url()` / redaction runs before any identity computation,
  logging, or Tavily call (`source_id_for()`, `_identity_claim()`,
  `extract_with_tavily()` all receive already-redacted/canonical values).
- No secret-looking value (`TAVILY_API_KEY`, tokens) is ever written into a
  note, log, or committed file; `.env` is excluded via `.gitignore`, and
  `.env.example` contains no real values.
- Tavily is never reachable for a URL `is_safe_public_url_for_tavily()`
  rejects; private/authenticated/paywalled paths never reach
  `extract_with_tavily()`.
- Path handling in `_resolve_within()`, `_destination_candidates()`, and
  the identity lock never allows a write outside the resolved vault root.

### 3. Test coverage & độ tin cậy

Confirm at least one test exists for each of: identity lock timeout,
`--refresh-existing` (both the ambiguous-legacy-boundary failure and the
link-only-to-rich-content success path), HTML-vs-text detection
(`_looks_like_html_capture()` true and false branches), duplicate matching
(v2 and legacy canonicalization), and Tavily fallback (`auto`/`basic`/
`advanced`, including the `TavilyConfigurationError` path). Flag any of
these with zero coverage, and flag any test removed from
`tests/test_save_capture.py` in recent history without an equivalent
replacement covering the same branch.

If the test suite fails to run at all (import error, interpreter missing,
etc.), record that itself as a **Nghiêm trọng** finding under this axis
before any other axis-3 finding — a broken dev environment undermines
confidence in every other check.

### 4. Plugin/marketplace health

- `name` and `version` agree across `plugin.json`,
  `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and
  `.codex-plugin/plugin.json`.
- Each `skills/*/agents/openai.yaml` (where present) matches its
  `SKILL.md` frontmatter `name`.
- `claude plugin list` shows no failed-to-load entries.
- `claude plugin marketplace list` has no stale/orphaned marketplace
  pointing at a worktree or path whose manifest no longer matches its
  registered name.
- `tests/test_repository.py::test_manifest_and_skill_metadata` passes.

## Phase 2 — Carry-over check

Find the most recent file in `docs/audits/` by filename date. **Skip this
phase and omit the "Việc tồn đọng" section entirely** if `docs/audits/` has
no prior report. Otherwise, for each unchecked `- [ ]` item in that prior
report, re-verify it against the current repository and mark it resolved
(`- [x]`, with the `file:line` that fixed it) or still open (`- [ ]`,
unchanged) in the new report. If an item can't be conclusively re-verified
(e.g. it depended on manual/browser testing, not something greppable),
leave it open rather than guessing, and note why it couldn't be confirmed.

## Phase 3 — Severity

Classify each new finding as exactly one of:

- **Nghiêm trọng** — correctness or security impact.
- **Nên sửa** — maintenance risk or missing coverage, not actively broken.
- **Ghi nhận** — minor observation, no action needed now.

## Phase 4 — Report and reply

Write `docs/audits/YYYY-MM-DD-project-health.md` using this exact
structure:

```markdown
# Project Health Audit — YYYY-MM-DD

## Snapshot
- HEAD: <sha> [<branch>]
- git status: <clean / N files changed>
- Skills: <list>
- Test suite: <passed>/<total>

## Scorecard
| Trục | Trạng thái |
|---|---|
| Docs ↔ code | ✅/⚠️/❌ |
| Bảo mật & quyền truy cập | ✅/⚠️/❌ |
| Test coverage & độ tin cậy | ✅/⚠️/❌ |
| Plugin/marketplace health | ✅/⚠️/❌ |

## Việc tồn đọng từ lần audit trước
- [x|] <item> — <resolution evidence, or "vẫn còn" with why>

## Finding mới theo trục
### Docs ↔ code
- **<mức độ>** `file:line` — <mô tả> — <bằng chứng> — <đề xuất xử lý>

### Bảo mật & quyền truy cập
...

### Test coverage & độ tin cậy
...

### Plugin/marketplace health
...
```

Then reply in chat with only: the scorecard table, the top 1-3 action
items, and the report file's path — never the full report text.
