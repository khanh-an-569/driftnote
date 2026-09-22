# Project Health Audit — 2026-09-22

## Snapshot
- HEAD: `e78ee11dcac10ef6b1f277ebd31e6ef31f163f29` [`worktree-project-audit-framework`]
- git status: clean (`git status --porcelain` produced no output)
- Skills: `skills/obsidian-clip-beautifier/SKILL.md`, `skills/obsidian-excalidraw-mindmap/SKILL.md`, `skills/web-to-obsidian/SKILL.md`
- Test suite: 143/143 passed (`python -m unittest discover -s tests` → `Ran 143 tests in 1.915s` / `OK`). One test in this run intentionally exercises the error path of `skills/obsidian-excalidraw-mindmap/scripts/generate_excalidraw.py` and prints `{"status": "error", "error": "Outline is missing a non-empty 'title'."}` to stdout as designed CLI error output — not a failure.

## Scorecard
| Trục | Trạng thái |
|---|---|
| Docs ↔ code | ⚠️ |
| Bảo mật & quyền truy cập | ✅ |
| Test coverage & độ tin cậy | ⚠️ |
| Plugin/marketplace health | ✅ |

## Finding mới theo trục

### Docs ↔ code
- **Nên sửa** `skills/web-to-obsidian/references/browser-capture.md:37` — Doc claims Quarto "warnings" (as well as "war stories") map to the Obsidian `warning` callout, but `skills/web-to-obsidian/scripts/save_capture.py`'s `_CALLOUT_TYPES` dict (lines 198–211) only contains a `"war-story": "warning"` entry — there is no `"warning"` key. — Reproduced: `html_to_markdown('<article><details class="callout-warning"><summary>Careful</summary><p>Some warning text</p></details></article>', 'https://example.com/')` renders `> [!note]- Careful`, not `> [!warning]- Careful`, because `_render_details()` (lines 583–602) only matches classes whose `callout-<type>` suffix is a key in `_CALLOUT_TYPES`; `callout-warning` falls through to the `"note"` default. — Đề xuất: either add a `"warning": "warning"` entry to `_CALLOUT_TYPES`, or correct the doc to say only "war stories" map to `warning`.

Everything else checked against the code agreed exactly:
- `SKILL.md` step 1's vault-resolution order (CLI arg → `WEB_TO_OBSIDIAN_VAULT_PATH`/`OBSIDIAN_VAULT_PATH` → `driftnote.yaml` `vault_root` → ask) matches `resolve_vault()` (`save_capture.py:966-983`) exactly, including "never guess, ask only after resolution fails" (raises `CaptureError` at 979-983 rather than guessing).
- `SKILL.md` step 8 and `README.md:173`'s Excalidraw-consent paragraph both describe the same behavior: a conversational chat question after reporting `created`/`duplicate`/`refreshed`, never a plugin dialog, and never auto-created.
- `browser-capture.md`'s HTML conversion boundary (heading offset, TOC-to-`[!toc]-` callout with same-note heading links, lightbox repair, ignored tags/scripts/forms) matches `html_to_markdown()`/`_HtmlMarkdownRenderer` (`save_capture.py:829-853`, `197-262`, `683-763`) line for line, verified by reading the renderer's tag dispatch and TOC-fragment resolution logic.
- `note-schema.md`'s `--content-file`/`--html-file` semantics (HTML auto-detected via structure, explicit `--html-file` rejected if it isn't HTML, refresh preserves `Ghi chú của tôi`) match `_looks_like_html_capture()` (`save_capture.py:856-877`) and `run_capture()`'s branching at `save_capture.py:1683-1708`.
- `tavily.md`'s connected-Extract-tool paragraph and `--tavily auto` claim ("auto runs only when both source content and selection are empty") match `run_capture()`'s `needs_content` computation (`save_capture.py:1714-1717`) and `extract_with_tavily()` raising `TavilyConfigurationError` when `TAVILY_API_KEY` is unset (`save_capture.py:1339-1342`), caught and warned about at `save_capture.py:1737-1739`.

### Bảo mật & quyền truy cập
No findings. Verified:
- `sanitize_url()` (`save_capture.py:1660`) runs before `source_id_for()` (`1667`), `_identity_claim()` (`1820`), and every `extract_with_tavily()` call (`1727`, inside the loop that starts at `1725`); `args.url` is read raw only at `1660` and `1719` (the latter itself calls `sanitize_url()` internally at `1184`) — no raw URL is logged or printed anywhere else in the file (`grep -n "args.url"` returns only those two lines).
- `.gitignore:2-4` ignores `.env` and `.env.*` but un-ignores `.env.example`; `.env.example` contains no real secret (`TAVILY_API_KEY=` is empty).
- `is_safe_public_url_for_tavily()` (`save_capture.py:1182-1203`) rejects non-`http(s)` schemes via `sanitize_url()`'s own scheme check (`_normalized_url_parts()`, `save_capture.py:999-1000`), confirmed empirically: `is_safe_public_url_for_tavily('file:///etc/passwd')` → `(False, 'invalid URL')`. It also rejects `localhost`/`.local`/`.internal`/`.localhost` hosts and non-global IPs, and is called (`run_capture()`, `save_capture.py:1719`) before any `extract_with_tavily()` call.
- `_resolve_within()` (`save_capture.py:1393-1407`) is applied to both `destination_folder` (`1766`) and the final `destination` (`1777`) before any write, and `run_capture()` raises `CaptureError` if either falls outside the vault root — matching `tests/test_save_capture.py:1234` (`test_destination_cannot_escape_vault`).

### Test coverage & độ tin cậy
- **Nên sửa** `skills/web-to-obsidian/scripts/save_capture.py:1723-1743` — The `tavily="auto"` dispatch loop (`depths = ["basic", "advanced"]` when not explicitly `basic`/`advanced`) that retries `advanced` after `basic` returns insufficient content or raises a plain `CaptureError`, as described in `skills/web-to-obsidian/references/tavily.md:17` ("Retry `advanced` at most once when basic extraction fails..."), has no test in `tests/test_save_capture.py` that exercises it through `run_capture()`. `grep -n "extract_with_tavily" tests/test_save_capture.py` shows every mock of `extract_with_tavily` is a single `return_value=`/`side_effect=AssertionError(...)`; no test uses a two-step `side_effect=[...]` list or asserts `call_count == 2`, so the basic→advanced fallback sequence inside `run_capture()` is untested (the "advanced" depth is only exercised as a direct unit test of `extract_with_tavily()` itself, e.g. `tests/test_save_capture.py:1012-1052`, which bypasses `run_capture()`'s loop entirely). Đề xuất: add a test that mocks `extract_with_tavily` with `side_effect=[<short basic result>, <longer advanced result>]` under `tavily="auto"` and asserts it was called twice with `"basic"` then `"advanced"`.

All other required branches have covering tests:
- Identity lock timeout → `tests/test_save_capture.py:1373` (`test_identity_lock_timeout_fails_closed`).
- `--refresh-existing` ambiguous-legacy-boundary failure → `tests/test_save_capture.py:514` (`test_refresh_legacy_note_fails_closed_on_ambiguous_personal_notes_boundary`); link-only-to-rich-content success → `tests/test_save_capture.py:610` (`test_refresh_link_only_note_adds_source_and_removes_warning`).
- `_looks_like_html_capture()` true branch → `tests/test_save_capture.py:100` (`test_content_file_with_html_is_detected_and_preserves_links`); false branch → `tests/test_save_capture.py:188` (`test_markdown_code_example_is_not_treated_as_html_capture`).
- Duplicate matching, v2 → `tests/test_save_capture.py:1427`/`1448` (trailing-slash/query-order identity); legacy via v2 canonicalization → `tests/test_save_capture.py:1469` (`test_v2_canonicalization_detects_legacy_duplicate`).
- Tavily `auto` (with `TavilyConfigurationError`) → `tests/test_save_capture.py:929` (`test_missing_tavily_key_reports_configuration_cause`); `basic` → `tests/test_save_capture.py:984` (`test_explicit_tavily_depth_supplements_existing_content`).
- No test was removed from `tests/test_save_capture.py` in recent history without an equivalent replacement: `git log -p --follow -- tests/test_save_capture.py | grep "^-    def test_"` shows exactly one removed test name (`test_canonicalize_removes_tracking_and_sorts_query`), and the same diff hunk shows it renamed in place to `test_canonicalize_removes_tracking_without_reordering_or_trimming_path`, covering the same `canonicalize_url()` behavior under its corrected (non-reordering) semantics.
- The full suite ran (no import error/interpreter issue): 143/143 passed, matching the Phase 0 snapshot.

### Plugin/marketplace health
No findings. Verified:
- `plugin.json` and `.claude-plugin/plugin.json` agree: `diff <(...) <(...)` produced no output (exit code 0), both reporting `driftnote 0.5.0`.
- `.claude-plugin/marketplace.json` lists `driftnote` → `source: "./"`, matching the installed marketplace entry from `claude plugin marketplace list` (`driftnote` → Source: Directory `E:\skill`, the main checkout this worktree branched from).
- `.codex-plugin/plugin.json` also reports `driftnote 0.5.0`, matching the other two manifests.
- Each `skills/*/agents/openai.yaml`'s `interface.display_name` is the title-cased form of its `SKILL.md` frontmatter `name` for all three skills (`web-to-obsidian` → "Web to Obsidian", `obsidian-clip-beautifier` → "Obsidian Clip Beautifier", `obsidian-excalidraw-mindmap` → "Obsidian Excalidraw Mindmap").
- `claude plugin list` shows `driftnote@driftnote` version `0.5.0`, Status: `✔ enabled` — no failed-to-load entries among any installed plugin.
- `claude plugin marketplace list` shows no stale/orphaned marketplace entries; the `driftnote` marketplace's directory manifest name/version matches its registered name.
- `python -m unittest tests.test_repository -v` → 6/6 passed, including `test_manifest_and_skill_metadata`.
