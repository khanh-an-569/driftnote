# Project Health Audit Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the driftnote maintainer a repeatable, on-demand way to audit the whole repository's health (docs↔code drift, security boundaries, test coverage, plugin/marketplace packaging) and see progress tracked across runs.

**Architecture:** A single instructions file (`docs/project-audit-framework.md`) that Claude follows verbatim when asked to run an audit; each run writes a dated, self-contained report to `docs/audits/`. Purely documentation — no application code, no new Skill, no plugin manifest changes.

**Tech Stack:** Markdown only. Verification uses the existing tools already in this repo: `git`, `python -m unittest`, `claude plugin` CLI.

## Global Constraints

- Stays entirely under `docs/` — do not add a `skills/project-health-audit/` directory, do not touch `plugin.json`, `.claude-plugin/*`, `.codex-plugin/*`, `agents/openai.yaml`, or `tests/test_repository.py`'s `expected_skill_names` (per spec Non-goals).
- On-demand only — no cron, no CI hook, no scheduled task.
- Every finding in every report must cite concrete evidence (`file:line`, or a command and its literal output) — never a speculative or vague finding.
- Report files in `docs/audits/` are write-once: each run creates a new dated file, never edits a prior one.
- First-ever run has no prior report to carry over from — the carry-over section is omitted entirely on that run, not left as an empty heading.

---

### Task 1: Write the audit framework instructions file

**Files:**
- Create: `docs/project-audit-framework.md`

**Interfaces:**
- Produces: the exact report structure (heading names, table columns, severity labels `Nghiêm trọng`/`Nên sửa`/`Ghi nhận`) that Task 2's report file must match verbatim.

- [ ] **Step 1: Write the framework file**

Create `docs/project-audit-framework.md` with this exact content:

```markdown
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
- Each `skills/*/agents/openai.yaml`'s `interface.default_prompt`
  references the skill by its `SKILL.md` frontmatter `name`, and
  `interface.display_name` is that name in title case.
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

Findings classified **Nghiêm trọng** or **Nên sửa** are written as
unchecked `- [ ]` action items so the next run's Phase 2 can find them;
**Ghi nhận** findings are written as plain bullets with no checkbox, since
they carry no follow-up action.

Each axis section lists its findings first (if any), then records what was
checked and confirmed clean, with the same evidence discipline (`file:line`
or command output) — so audits stay comparable across runs.

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
- [x] <item> — đã xử lý, xem `file:line`
- [ ] <item> — vẫn còn, xem `file:line` hoặc lý do chưa xác minh được

## Finding mới theo trục
### Docs ↔ code
- [ ] **<mức độ>** `file:line` — <mô tả> — <bằng chứng> — <đề xuất xử lý>

### Bảo mật & quyền truy cập
...

### Test coverage & độ tin cậy
...

### Plugin/marketplace health
...
```

Then reply in chat with only: the scorecard table, the top 1-3 action
items, and the report file's path — never the full report text.
```

- [ ] **Step 2: Verify the file was written correctly**

Run:
```bash
test -f docs/project-audit-framework.md && wc -l docs/project-audit-framework.md
```
Expected: file exists, non-zero line count (~140-160 lines).

- [ ] **Step 3: Self-review against the design spec**

Open `docs/superpowers/specs/2026-09-22-project-audit-framework-design.md`
side by side with the new file and confirm:
- All four axis names match exactly (Docs ↔ code / Bảo mật & quyền truy
  cập / Test coverage & độ tin cậy / Plugin/marketplace health).
- The report format block matches the spec's "Report format" section
  structurally (same headings, same table columns, same severity labels).
- No `TBD`/`TODO`/placeholder text anywhere in the file — every checklist
  bullet names a real, existing function or file path (spot-check 3 of
  them against the actual codebase with `grep`).

- [ ] **Step 4: Commit**

```bash
git add docs/project-audit-framework.md
git commit -m "docs: add project health audit framework instructions"
```

---

### Task 2: Run the first real audit and produce the first dated report

**Files:**
- Create: `docs/audits/2026-09-22-project-health.md`

**Interfaces:**
- Consumes: `docs/project-audit-framework.md` from Task 1 (follow it exactly).

- [ ] **Step 1: Create the audits directory and run Phase 0**

```bash
mkdir -p docs/audits
git rev-parse HEAD
git branch --show-current
git status --porcelain
find skills -iname "SKILL.md"
python -m unittest discover -s tests
```

Record the literal output of each command — these become the "Snapshot"
section of the report.

- [ ] **Step 2: Work through Phase 1, axis 1 (Docs ↔ code)**

For each bullet listed under "1. Docs ↔ code" in
`docs/project-audit-framework.md`, open the named doc section and the
named code symbol side by side (`grep -n` for the function/class name in
`skills/web-to-obsidian/scripts/save_capture.py`) and confirm they agree.
Write down any mismatch with its `file:line` evidence.

- [ ] **Step 3: Work through Phase 1, axis 2 (Bảo mật & quyền truy cập)**

For each bullet under "2. Bảo mật & quyền truy cập", grep the named
function (e.g. `sanitize_url`, `is_safe_public_url_for_tavily`,
`_resolve_within`) and trace its callers to confirm the ordering/boundary
claim holds. Check `.gitignore` for `.env` and confirm `.env.example` has
no non-empty secret-looking values. Write down any gap with evidence.

- [ ] **Step 4: Work through Phase 1, axis 3 (Test coverage & độ tin cậy)**

For each branch listed under "3. Test coverage", grep
`tests/test_save_capture.py` for a test name that exercises it (e.g.
`grep -n "def test_" tests/test_save_capture.py`) and confirm at least one
match per branch. Cross-reference the pass/fail count captured in Step 1.

- [ ] **Step 5: Work through Phase 1, axis 4 (Plugin/marketplace health)**

```bash
diff <(python -c "import json;print(json.load(open('plugin.json'))['name'],json.load(open('plugin.json'))['version'])") \
     <(python -c "import json;print(json.load(open('.claude-plugin/plugin.json'))['name'],json.load(open('.claude-plugin/plugin.json'))['version'])")
claude plugin list
claude plugin marketplace list
python -m unittest tests.test_repository -v
```

Record any mismatch or failed-to-load/stale entry with evidence.

- [ ] **Step 6: Skip Phase 2 (no prior report exists)**

Confirm `docs/audits/` had no files before Step 1's `mkdir -p` (this is the
first-ever run) — omit the "Việc tồn đọng" section from the report
entirely rather than writing an empty heading.

- [ ] **Step 7: Classify every finding from Steps 2-5 by severity**

Apply the three labels from Phase 3 in `docs/project-audit-framework.md`
(Nghiêm trọng / Nên sửa / Ghi nhận) to each finding recorded above.

- [ ] **Step 8: Write the report file**

Write `docs/audits/2026-09-22-project-health.md` following the exact
structure from Phase 4 of `docs/project-audit-framework.md`, filled in with
the real snapshot output (Step 1) and real findings (Steps 2-7).

- [ ] **Step 9: Verify the report file**

```bash
test -f docs/audits/2026-09-22-project-health.md
grep -c "^##" docs/audits/2026-09-22-project-health.md
```
Expected: file exists; at least 3 `##` headings (Snapshot, Scorecard,
Finding mới theo trục — "Việc tồn đọng" is correctly absent on this run).

- [ ] **Step 10: Commit**

```bash
git add docs/audits/2026-09-22-project-health.md
git commit -m "docs: run first project health audit"
```

- [ ] **Step 11: Reply in chat**

Per Phase 4's instruction, reply with only the scorecard table, the top
1-3 action items, and the path to the report file — not the full report
text.
