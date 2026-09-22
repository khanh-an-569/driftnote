# Design: project health audit framework

Date: 2026-09-22
Status: Approved

## Summary

Driftnote has no standing process for periodically checking its own health
as a project — the review just run against the current diff (docs/code
drift, hybrid-capture-method bypassing the new link-loss guard, duplicated
fence-detection logic) was ad hoc and diff-scoped. Add a maintainer-only,
on-demand audit framework: a checklist document Claude follows when asked,
covering the whole repository rather than a single diff, that produces a
dated report file plus a short chat summary each time it runs.

This is tooling for whoever maintains the driftnote repository, not a
capability of the driftnote plugin itself. It intentionally does not become
a fourth `skills/` entry, so it is never bundled into what end users install
from the marketplace.

## Goals

- Give the maintainer a repeatable way to ask Claude "how healthy is this
  project right now?" and get evidence-backed findings, not vibes.
- Cover four axes agreed with the maintainer: docs↔code consistency,
  security & access boundaries, test coverage & reliability, and
  plugin/marketplace packaging health.
- Track findings across runs: each run reads the most recent prior report,
  re-checks its still-open action items, and reports whether they were
  resolved before listing new findings — so the audit shows progress, not
  just a fresh unrelated snapshot every time.
- Every finding cites concrete evidence (`file:line`, or a command and its
  output) — mirroring the discipline used by the `/code-review` skill run
  earlier in this session (candidates get verified, not just asserted).

## Non-goals

- Not a Claude Code Skill/slash-command. No changes to `plugin.json`,
  `.claude-plugin/*`, `.codex-plugin/*`, `agents/openai.yaml`, or
  `tests/test_repository.py`'s `expected_skill_names` — this stays entirely
  under `docs/`, invoked by pointing Claude at the framework file directly.
- Not scheduled/automatic. The maintainer explicitly triggers each run;
  no cron, no CI hook.
- Not a replacement for `/code-review` on individual PRs/diffs — that skill
  remains the right tool for reviewing a specific change. This framework is
  for whole-repository health checks, run independently of any particular
  diff.
- Not exhaustive static analysis or a security scanner — findings are
  scoped to what a careful manual read of this specific, single-maintainer,
  stdlib-only codebase can confirm with evidence, not a general-purpose
  vulnerability sweep.

## Design

### Components and location

- `docs/project-audit-framework.md` — the framework itself: purpose, how to
  invoke it, the four axes with concrete (project-specific, not generic)
  checklist items, the report format, and the carry-over mechanism. This is
  the only file the maintainer needs to reference to trigger a run
  ("chạy audit theo docs/project-audit-framework.md").
- `docs/audits/YYYY-MM-DD-project-health.md` — one dated report per run,
  never overwritten, so history accumulates and can be diffed/read back.

### Process

**Phase 0 — Snapshot.** Record `git status --porcelain`, the current HEAD
commit and branch, the list of skills under `skills/*/SKILL.md`, and the
result of running the test suite (`python -m unittest discover -s tests`).
This makes each report self-contained evidence of the repo state at run
time, independent of later changes.

**Phase 1 — Four-axis check.** For each axis, the framework file lists
concrete checks specific to this repository (not a generic template):

1. **Docs ↔ code.** For each documented flag/behavior in `SKILL.md` and
   `skills/web-to-obsidian/references/*.md`, confirm the corresponding code
   path in `save_capture.py` (or `generate_excalidraw.py` for the
   Excalidraw skill) actually implements what is documented — same method
   used earlier in this session to confirm `--allow-text-only` and the
   Tavily Extract connected-tool doc addition both match the code.
2. **Security & access boundaries.** URL redaction before identity/logging,
   no secrets in committed files (`.env` vs `.env.example`), the
   public-URL-only Tavily boundary, and any obvious injection/path-traversal
   risk in the stdlib-only scripts.
3. **Test coverage & reliability.** Enumerate the load-bearing branches
   (identity lock, `--refresh-existing`, HTML-vs-text detection, duplicate
   matching, Tavily fallback) and confirm each has at least one test; flag
   any test that was deleted/weakened without an equivalent replacement, and
   record the actual pass/fail count from Phase 0's test run.
4. **Plugin/marketplace health.** Name and version agreement across
   `plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
   `.codex-plugin/plugin.json`, and each skill's `agents/openai.yaml`; check
   `claude plugin list` / `claude plugin marketplace list` for stale or
   failed-to-load entries (the kind of drift found and fixed earlier this
   session, where a worktree-backed marketplace still under the old
   `web-to-obsidian` name broke plugin resolution).

**Phase 2 — Carry-over check.** Before writing new findings, read the most
recent file in `docs/audits/` (by filename date, skip if none exists yet).
For each of its unchecked action items, re-verify against the current code
whether it is now resolved; mark it resolved or still-open in the new
report instead of re-discovering it as a "new" finding.

**Phase 3 — Severity and evidence.** Classify every new finding as
**Nghiêm trọng** (correctness or security impact), **Nên sửa** (maintenance
risk, missing coverage), or **Ghi nhận** (minor observation, no action
needed now). Every finding must name the evidence (file:line, or the
command/output that demonstrates it) — no finding may be speculative.

**Phase 4 — Report and summary.** Write the full report to
`docs/audits/YYYY-MM-DD-project-health.md` using the format below, then
reply in chat with the scorecard table and the top 1-3 action items plus a
link to the full report file.

### Report format

```markdown
# Project Health Audit — YYYY-MM-DD

## Snapshot
- HEAD: <sha> [<branch>]
- git status: <clean / N files changed>
- Skills: <list from skills/*/SKILL.md>
- Test suite: <passed>/<total> (`python -m unittest discover -s tests`)

## Scorecard
| Trục | Trạng thái |
|---|---|
| Docs ↔ code | ✅ / ⚠️ / ❌ |
| Bảo mật & quyền truy cập | ✅ / ⚠️ / ❌ |
| Test coverage & độ tin cậy | ✅ / ⚠️ / ❌ |
| Plugin/marketplace health | ✅ / ⚠️ / ❌ |

## Việc tồn đọng từ lần audit trước
- [x] <item> — đã xử lý, xem `file:line`
- [ ] <item> — vẫn còn, xem lần audit trước: `docs/audits/<prior-file>.md`

(section omitted entirely on the first-ever run, when no prior report exists)

## Finding mới theo trục
### Docs ↔ code
- **[Nghiêm trọng|Nên sửa|Ghi nhận]** `file:line` — mô tả — bằng chứng — đề xuất xử lý

### Bảo mật & quyền truy cập
...

### Test coverage & độ tin cậy
...

### Plugin/marketplace health
...
```

### Edge cases

- **Uncommitted working-tree changes at run time.** The snapshot records
  `git status --porcelain` verbatim, and all four axes check the working
  tree as it stands (not just `HEAD`) — matching how the `/code-review` run
  earlier in this session included uncommitted changes in scope.
- **Test suite fails to run at all** (missing interpreter, import error).
  This is itself a top-severity ("Nghiêm trọng") finding under Test
  coverage & reliability, reported before any other axis 3 findings, since
  a broken dev environment undermines confidence in everything else.
- **No prior report exists** (first run ever). Phase 2 is skipped; the
  report's carry-over section is omitted rather than left as an empty
  placeholder heading.
- **A carried-over item can't be conclusively re-verified** (e.g., it
  depended on manual/browser testing, not something greppable). Keep it
  open rather than guessing; note why it couldn't be confirmed.

## Testing plan

There is no code to unit-test — this is a process document. Validation is:

1. Run the framework for real immediately after this design is approved,
   producing `docs/audits/2026-09-22-project-health.md` as the first-ever
   report (no carry-over section, per the edge case above).
2. Confirm the report follows the format exactly and every finding in it
   cites concrete evidence, before treating the framework doc itself as
   validated.
3. On the *second* real run (whenever the maintainer next triggers one),
   confirm the carry-over section correctly reflects which of the first
   run's action items were resolved in the meantime.
