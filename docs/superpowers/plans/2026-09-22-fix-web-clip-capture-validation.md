# Fix Web Clip Capture Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `driftnote:web-to-obsidian` from silently publishing a structurally broken note (wrong table of contents, hidden empty sections, content dropped during conversion, dead same-page links) when the only available source is flat Markdown or the HTML converter itself loses content, by adding a redirect-safe public-HTML fetch tier ahead of Tavily and a pre-write validation gate that fails closed with a new `needs-review` status — writing a labeled draft for a human to fix, never the main note — instead of publishing bad content.

**Architecture:** All work lands in the existing single-file helper `skills/web-to-obsidian/scripts/save_capture.py` (stdlib-only, no new dependencies) plus its test file `tests/test_save_capture.py` (stdlib `unittest`, matching repo convention — no `pytest`). Six small, independently testable detector functions (broken code spans, duplicate TOC destinations, empty sections, reported update date, structural content loss between HTML and Markdown, same-page fragment-to-heading resolution) are composed into one gate function that `run_capture()` consults once `title`/`captured_date`/`filename_title` are finalized, before any file is written; on failure it writes a `type: capture-review` draft under `Needs Review/` instead of the main note. A new `fetch_public_html()` tier reuses the existing Tavily safety gate (`is_safe_public_url_for_tavily`) and the existing HTML→Markdown converter (`html_to_markdown`), adding its own redirect-hop revalidation, size cap, and content-type check on top. Documentation in `SKILL.md`/`references/*.md` is updated last, once the new behavior actually exists. Syncing the fix to the actually-installed Codex plugin and recreating the one broken note in the vault are manual final steps, done only after everything above is live.

**Tech Stack:** Python 3 standard library only (`re`, `urllib.request`, `urllib.error`) inside `save_capture.py`; `unittest` + `unittest.mock` for tests, matching `tests/test_save_capture.py`'s existing style exactly (no `pytest`-only syntax, no fixture files — every other test in that file embeds Markdown/HTML as inline string literals, so new tests do the same).

## Global Constraints

- `save_capture.py` stays Python-standard-library-only — do not add a third-party import to the script itself (its own docstring at lines 1–7 states this).
- Tests live in `tests/test_save_capture.py` as methods on the existing `SaveCaptureTests(unittest.TestCase)` class; run them with `python -m unittest tests.test_save_capture.SaveCaptureTests.<test_name> -v` (repo convention — see `docs/superpowers/plans/2026-09-21-obsidian-excalidraw-mindmap.md:185`).
- Every new test embeds Markdown/HTML as an inline Python string literal in the test method, like every existing test in the file. Do not introduce a `tests/fixtures/` directory or copy real third-party page content verbatim — hand-author minimal snippets that reproduce the structural bug shape only.
- Any new network call must be gated by the existing `is_safe_public_url_for_tavily()` check before it fires — no fetch to localhost, private/internal hosts, or a URL that `sanitize_url()` flags as redacted.
- `needs-review` is a new terminal status. When `run_capture()` returns it, the *main* note (`type: source`) must never be created, refreshed, or overwritten — instead, a separate draft (`type: capture-review`) is written under `<folder>/Needs Review/`, never under the main folder directly. Verify both halves in the integration test: no `type: source` note was touched, and exactly one `type: capture-review` note exists under `Needs Review/`.
- New documentation lines in `SKILL.md`, `references/tavily.md`, and `references/browser-capture.md` follow the file's existing bilingual convention: one English sentence, then the Vietnamese equivalent, matching adjacent lines.

---

### Task 1: Detect a single backtick span that crosses a blank line

A real fenced code block always opens and closes with three backticks. Tavily's connected-extract Markdown sometimes wraps a whole shell transcript in a single backtick instead — and if that transcript contains a blank line (it always does, since it's a multi-command script), the span silently breaks at the blank line under normal Markdown parsing. Everything after that point, including lines like `# 2. Upload directly...`, is then read as ordinary Markdown, not code — which is exactly how a shell comment became a fake H1 heading in the Gemini File Search note. This task adds a detector for that exact shape.

**Files:**
- Modify: `skills/web-to-obsidian/scripts/save_capture.py` — insert new function after `_generate_toc_from_headings` (currently ends at line 826), before `html_to_markdown` (currently starts at line 829).
- Test: `tests/test_save_capture.py` — add new test methods to `SaveCaptureTests`, near the existing TOC tests around line 1533–1544.

**Interfaces:**
- Produces: `_find_unfenced_multiline_code_spans(content: str) -> list[tuple[int, int]]` — 1-indexed `(start_line, end_line)` pairs, one per detected broken span. Used by Task 5.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_save_capture.py` inside `SaveCaptureTests`:

```python
    def test_finds_broken_single_backtick_span_crossing_blank_line(self) -> None:
        content = (
            "### REST\n\n"
            "`# 1. Create a File Search store\n"
            "curl -X POST \"https://example.com\"\n\n"
            "# 2. Upload directly to File Search store\n\n"
            "curl -X POST \"https://example.com/upload\"`\n"
        )
        spans = save_capture._find_unfenced_multiline_code_spans(content)
        self.assertEqual(spans, [(3, 8)])

    def test_ignores_balanced_single_backtick_terms_on_their_own_line(self) -> None:
        content = (
            "## Section\n\n"
            "`gemini-embedding-001`\n\n"
            "## Next section\n\n"
            "Body text.\n"
        )
        self.assertEqual(save_capture._find_unfenced_multiline_code_spans(content), [])

    def test_ignores_spans_already_inside_triple_backtick_fences(self) -> None:
        content = (
            "## Section\n\n"
            "```text\n"
            "`half open\n\n"
            "still inside fence\n"
            "```\n\n"
            "## Next section\n\n"
            "Body text.\n"
        )
        self.assertEqual(save_capture._find_unfenced_multiline_code_spans(content), [])

    def test_flags_a_span_left_open_at_end_of_content(self) -> None:
        content = "## Section\n\n`opened but never closed\n\nmore text\n"
        self.assertEqual(
            save_capture._find_unfenced_multiline_code_spans(content),
            [(3, 5)],
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests.test_finds_broken_single_backtick_span_crossing_blank_line -v`
Expected: FAIL with `AttributeError: module 'save_capture' has no attribute '_find_unfenced_multiline_code_spans'`

- [ ] **Step 3: Implement the detector**

Insert into `skills/web-to-obsidian/scripts/save_capture.py` immediately after the `_generate_toc_from_headings` function (after its closing `return "\n".join(toc_lines)` line, currently line 826):

```python
def _find_unfenced_multiline_code_spans(content: str) -> list[tuple[int, int]]:
    """Report 1-indexed line ranges where a lone backtick code span crosses a
    blank line. A real ``` fence always closes before content resumes; a
    single backtick that survives a blank-line paragraph break never really
    closed, so everything inside — including shell comments that look like
    "# Step 2" — gets parsed as ordinary Markdown, not code.
    """

    spans: list[tuple[int, int]] = []
    in_triple_fence = False
    open_span_start: int | None = None
    saw_blank_since_open = False

    lines = content.splitlines()
    for line_number, line in enumerate(lines, start=1):
        if _CODE_FENCE_PATTERN.match(line):
            in_triple_fence = not in_triple_fence
            continue
        if in_triple_fence:
            continue
        if open_span_start is not None and not line.strip():
            saw_blank_since_open = True
        if line.count("`") % 2 == 1:
            if open_span_start is None:
                open_span_start = line_number
                saw_blank_since_open = False
            else:
                if saw_blank_since_open:
                    spans.append((open_span_start, line_number))
                open_span_start = None
                saw_blank_since_open = False
    if open_span_start is not None:
        spans.append((open_span_start, len(lines)))
    return spans
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests -k unfenced -v` (or run each of the four test names from Step 1 individually)
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/web-to-obsidian/scripts/save_capture.py tests/test_save_capture.py
git commit -m "feat: detect single-backtick code spans that cross a blank line"
```

---

### Task 2: Detect duplicate table-of-contents destinations

Obsidian links to a heading by its full ancestor path (`[[#Parent#Child]]`). Two sibling headings with the literal same text under the same parent — which the Gemini page genuinely has (two `### Python` subsections under "Siêu dữ liệu của tệp") — produce two TOC entries with the identical destination, which Obsidian cannot disambiguate. This task adds a detector so the write gate (Task 5) can catch that instead of publishing an ambiguous TOC.

**Files:**
- Modify: `skills/web-to-obsidian/scripts/save_capture.py` — insert two new functions directly after Task 1's `_find_unfenced_multiline_code_spans`.
- Test: `tests/test_save_capture.py` — add new test methods near Task 1's tests.

**Interfaces:**
- Produces: `_extract_toc_block(content: str) -> str` — the `> [!toc]...` callout lines only (empty string if none). Used by `_collect_content_review_issues` in Task 5.
- Produces: `_find_duplicate_toc_destinations(toc: str) -> list[str]` — sorted list of destination strings (the part before `|` inside `[[...]]`) that appear more than once. Used by Task 5.

- [ ] **Step 1: Write the failing tests**

```python
    def test_extracts_only_the_toc_callout_block(self) -> None:
        content = (
            "> [!toc]- Table of contents\n"
            "> - [[#A]]\n"
            ">   - [[#A#B|B]]\n\n"
            "# A\n\nBody with a [[#A#B|B]] link too.\n"
        )
        block = save_capture._extract_toc_block(content)
        self.assertIn("[[#A#B|B]]", block)
        self.assertNotIn("Body with a", block)

    def test_returns_empty_string_when_no_toc_block_exists(self) -> None:
        self.assertEqual(save_capture._extract_toc_block("# A\n\nBody.\n"), "")

    def test_finds_duplicate_toc_destinations(self) -> None:
        toc = (
            "> [!toc]- Table of contents\n"
            "> - [[#Section]]\n"
            ">   - [[#Section#Python|Python]]\n"
            ">   - [[#Section#Python|Python]]\n"
            ">   - [[#Section#REST|REST]]\n"
        )
        self.assertEqual(
            save_capture._find_duplicate_toc_destinations(toc),
            ["#Section#Python"],
        )

    def test_no_duplicates_when_every_destination_is_unique(self) -> None:
        toc = (
            "> [!toc]- Table of contents\n"
            "> - [[#Section]]\n"
            ">   - [[#Section#Python|Python]]\n"
            ">   - [[#Section#REST|REST]]\n"
        )
        self.assertEqual(save_capture._find_duplicate_toc_destinations(toc), [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests.test_finds_duplicate_toc_destinations -v`
Expected: FAIL with `AttributeError: module 'save_capture' has no attribute '_find_duplicate_toc_destinations'`

- [ ] **Step 3: Implement both functions**

Insert into `skills/web-to-obsidian/scripts/save_capture.py` directly after Task 1's function:

```python
def _extract_toc_block(content: str) -> str:
    """Return only the ``> [!toc]`` callout's lines, or "" if there is none."""

    lines = content.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("> [!toc]")), None)
    if start is None:
        return ""
    end = start + 1
    while end < len(lines) and lines[end].startswith(">"):
        end += 1
    return "\n".join(lines[start:end])


_TOC_WIKILINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def _find_duplicate_toc_destinations(toc: str) -> list[str]:
    """Return wikilink destinations that appear more than once in ``toc``."""

    seen: dict[str, int] = {}
    for match in _TOC_WIKILINK_PATTERN.finditer(toc):
        destination = match.group(1)
        seen[destination] = seen.get(destination, 0) + 1
    return sorted(destination for destination, count in seen.items() if count > 1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests -k toc_dest -v` (and the two `_extract_toc_block` tests)
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/web-to-obsidian/scripts/save_capture.py tests/test_save_capture.py
git commit -m "feat: detect duplicate table-of-contents destinations"
```

---

### Task 3: Detect a heading with no body before the next heading

The Gemini note's "## Giá" section has nothing between it and "## Bước tiếp theo" — the pricing content was never captured. This task adds a detector that flags a heading as empty only when nothing (no prose, no code, no child heading) follows it before the next sibling-or-shallower heading or end of content — a heading that is immediately followed by a *deeper* child heading (a completely normal docs pattern) must not be flagged.

**Files:**
- Modify: `skills/web-to-obsidian/scripts/save_capture.py` — insert after Task 2's functions.
- Test: `tests/test_save_capture.py` — add new test methods near Task 2's tests.

**Interfaces:**
- Produces: `_find_empty_sections(content: str) -> list[str]` — heading text (not full path) for each empty section, in document order. Used by Task 5.

- [ ] **Step 1: Write the failing tests**

```python
    def test_finds_heading_with_no_body_before_next_sibling_heading(self) -> None:
        content = (
            "## Giá\n\n"
            "## Bước tiếp theo\n\n"
            "Trừ phi có lưu ý khác...\n"
        )
        self.assertEqual(save_capture._find_empty_sections(content), ["Giá"])

    def test_does_not_flag_a_parent_heading_that_only_contains_a_child_heading(
        self,
    ) -> None:
        content = (
            "## Các điểm hạn chế\n\n"
            "### Giới hạn số lượng yêu cầu\n\n"
            "Aware API có các giới hạn sau.\n"
        )
        self.assertEqual(save_capture._find_empty_sections(content), [])

    def test_flags_the_final_heading_when_nothing_follows_it(self) -> None:
        content = "## Intro\n\nBody text.\n\n## Trailing\n"
        self.assertEqual(save_capture._find_empty_sections(content), ["Trailing"])

    def test_does_not_flag_a_heading_followed_only_by_a_code_fence_body(self) -> None:
        content = "## Example\n\n```bash\necho hi\n```\n\n## Next\n\nBody.\n"
        self.assertEqual(save_capture._find_empty_sections(content), [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests.test_finds_heading_with_no_body_before_next_sibling_heading -v`
Expected: FAIL with `AttributeError: module 'save_capture' has no attribute '_find_empty_sections'`

- [ ] **Step 3: Implement the detector**

Insert into `skills/web-to-obsidian/scripts/save_capture.py` directly after Task 2's functions:

```python
def _find_empty_sections(content: str) -> list[str]:
    """Report heading text for a section with no body before the next
    sibling/ancestor heading or end of content. A heading immediately
    followed by a deeper child heading is not empty — the child is its body.
    """

    lines = content.splitlines()
    headings: list[tuple[int, int, str]] = []
    in_fence = False
    for index, line in enumerate(lines):
        if _CODE_FENCE_PATTERN.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _MARKDOWN_HEADING_PATTERN.match(line)
        if match:
            headings.append((index, len(match.group(1)), match.group(2).strip()))

    empty: list[str] = []
    for position, (line_index, level, text) in enumerate(headings):
        if position + 1 < len(headings):
            next_index, next_level, _ = headings[position + 1]
        else:
            next_index, next_level = len(lines), None
        if next_level is not None and next_level > level:
            continue
        has_body = False
        fence_state = False
        for body_line in lines[line_index + 1 : next_index]:
            if _CODE_FENCE_PATTERN.match(body_line):
                fence_state = not fence_state
                has_body = True
                continue
            if fence_state:
                has_body = True
                continue
            if body_line.strip():
                has_body = True
        if not has_body:
            empty.append(text)
    return empty
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests -k empty_section -v` (and the "final heading"/"code fence body" tests)
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/web-to-obsidian/scripts/save_capture.py tests/test_save_capture.py
git commit -m "feat: detect headings with no body content"
```

---

### Task 4: Extract a reported "last updated" date for visibility

We cannot cheaply prove a Tavily extraction is stale without re-fetching the live page at write time (expensive, a new network failure mode, and out of scope). What we *can* do cheaply: surface whatever "last updated" date the page itself reports, in the capture result, so the person reviewing the note can judge freshness themselves — exactly what caught the 2026-08-19-vs-2026-09-18 mismatch in the Gemini note.

**Files:**
- Modify: `skills/web-to-obsidian/scripts/save_capture.py` — insert after Task 3's function.
- Test: `tests/test_save_capture.py` — add new test methods near Task 3's tests.

**Interfaces:**
- Produces: `_extract_reported_update_date(content: str) -> str | None` — an `"YYYY-MM-DD"` string or `None`. Used by Task 5.

- [ ] **Step 1: Write the failing tests**

```python
    def test_extracts_vietnamese_last_updated_date(self) -> None:
        content = "...\n\nCập nhật lần gần đây nhất: 2026-08-19 UTC.\n"
        self.assertEqual(
            save_capture._extract_reported_update_date(content), "2026-08-19"
        )

    def test_extracts_english_last_updated_date(self) -> None:
        content = "...\n\nLast updated: 2026-08-19.\n"
        self.assertEqual(
            save_capture._extract_reported_update_date(content), "2026-08-19"
        )

    def test_returns_none_when_no_update_date_is_present(self) -> None:
        self.assertIsNone(save_capture._extract_reported_update_date("No date here."))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests.test_extracts_vietnamese_last_updated_date -v`
Expected: FAIL with `AttributeError: module 'save_capture' has no attribute '_extract_reported_update_date'`

- [ ] **Step 3: Implement the extractor**

Insert into `skills/web-to-obsidian/scripts/save_capture.py` directly after Task 3's function:

```python
_UPDATE_DATE_PATTERN = re.compile(
    r"(?:C[aậ]p nh[aậ]t l[aầ]n g[aầ]n đ[aâ]y nh[aấ]t|Last updated)\s*:\s*"
    r"(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


def _extract_reported_update_date(content: str) -> str | None:
    """Best-effort extraction of a page's self-reported last-updated date,
    for visibility only — never used to block a write.
    """

    match = _UPDATE_DATE_PATTERN.search(content)
    return match.group(1) if match else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests -k update_date -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/web-to-obsidian/scripts/save_capture.py tests/test_save_capture.py
git commit -m "feat: extract a page's self-reported last-updated date"
```

---

### Task 5: Wire a pre-write validation gate into `run_capture()`

This is where the four detectors stop being unused code and start protecting the vault: `run_capture()` must refuse to create or refresh the *main* note when the finalized content fails validation. Instead of writing nothing, it writes a separate, clearly-labeled draft — `type: capture-review`, `status: needs-review` — under `<folder>/Needs Review/`, so a human has something to open and fix rather than only a JSON error to relay. `find_duplicate()` already ignores this draft for free: `_read_note_identity` only recognizes `type: source` (existing code), so a `capture-review` note never blocks or gets confused with a real source note for the same URL.

**Files:**
- Modify: `skills/web-to-obsidian/scripts/save_capture.py`:
  - Insert `_collect_content_review_issues` after Task 4's function.
  - Insert `_render_review_note` directly after `_render_note` (currently ends at line 1501), before `_destination_candidates` (currently line 1504).
  - Insert `_write_review_note` directly after `_render_review_note`.
  - Modify `run_capture()` right after `captured_date = ...` is computed (currently line 1759), before `destination_folder_candidate = ...` (currently line 1761) — this is *later* than the `capture_method`/`tavily_depth` block, because the review draft's filename needs `title`/`filename_title`/`captured_date`, which aren't computed until this point.
  - Modify the `"refreshed"` return dict (currently lines 1838–1847) and the `"created"` return dict (currently lines 1900–1909) to include `reported_update_date`.
- Test: `tests/test_save_capture.py` — add new test methods after the existing TOC tests (after line 1544, before `if __name__ == "__main__":`).

**Interfaces:**
- Consumes: `_find_unfenced_multiline_code_spans`, `_extract_toc_block`, `_find_duplicate_toc_destinations`, `_find_empty_sections`, `_extract_reported_update_date` (Tasks 1–4); `_yaml_string`, `_yaml_list`, `_destination_candidates`, `_resolve_within` (existing).
- Produces: `_collect_content_review_issues(content: str) -> list[str]` — empty list means the content is safe to publish.
- Produces: `_render_review_note(*, title, source_id, source_url, canonical_url, source_url_redacted, captured, capture_method, review_issues, reported_update_date, content, tavily_request_id) -> str`.
- Produces: `_write_review_note(vault: Path, folder: str, captured_date: str, filename_title: str, source_id: str, note_text: str) -> Path` — raises `CaptureError` if no non-clobbering filename can be found.
- Produces (new `run_capture()` behavior): a result dict with `"status": "needs-review"`, `"review_issues": list[str]`, `"reported_update_date": str | None`, `"path"` pointing at the review draft (or `None` on `--dry-run`), alongside the existing `source_id`/`canonical_url`/`source_url_redacted`/`capture_method`/`link_only`/`warnings` keys.

- [ ] **Step 1: Write the failing unit test for the gate function**

```python
    def test_collect_content_review_issues_reports_broken_fence_duplicate_toc_and_empty_section(
        self,
    ) -> None:
        content = (
            "> [!toc]- Table of contents\n"
            "> - [[#REST]]\n"
            ">   - [[#REST#Python|Python]]\n"
            ">   - [[#REST#Python|Python]]\n\n"
            "## REST\n\n"
            "`# 1. Create a File Search store\n"
            "curl -X POST \"https://example.com\"\n\n"
            "# 2. Upload directly\n\n"
            "curl -X POST \"https://example.com/upload\"`\n\n"
            "## Giá\n\n"
            "## Bước tiếp theo\n\n"
            "Body.\n"
        )
        issues = save_capture._collect_content_review_issues(content)
        self.assertEqual(len(issues), 3)
        self.assertTrue(any("broken" in issue for issue in issues))
        self.assertTrue(any("REST#Python" in issue for issue in issues))
        self.assertTrue(any('"Giá"' in issue for issue in issues))

    def test_collect_content_review_issues_is_empty_for_clean_content(self) -> None:
        content = (
            "## Intro\n\nBody one.\n\n"
            "## Details\n\n```bash\n# a real shell comment\necho hi\n```\n\nBody two.\n"
        )
        self.assertEqual(save_capture._collect_content_review_issues(content), [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests.test_collect_content_review_issues_is_empty_for_clean_content -v`
Expected: FAIL with `AttributeError: module 'save_capture' has no attribute '_collect_content_review_issues'`

- [ ] **Step 3: Implement the gate function**

Insert into `skills/web-to-obsidian/scripts/save_capture.py` directly after Task 4's function:

```python
def _collect_content_review_issues(content: str) -> list[str]:
    """Return blocking reasons the generated source content should not be
    published as-is. An empty list means the content passed validation.
    """

    issues: list[str] = []

    for start_line, end_line in _find_unfenced_multiline_code_spans(content):
        issues.append(
            f"A single backtick opened on line {start_line} is not closed "
            f"before line {end_line}; the code fence is broken and any "
            "headings inside it were likely misread as real headings."
        )

    for destination in _find_duplicate_toc_destinations(_extract_toc_block(content)):
        issues.append(
            f"Table of contents entry `{destination}` appears more than once; "
            "Obsidian cannot navigate to a unique heading for it."
        )

    for heading in _find_empty_sections(content):
        issues.append(
            f'Section "{heading}" has no body content before the next heading.'
        )

    return issues
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests -k collect_content_review_issues -v`
Expected: 2 tests PASS

- [ ] **Step 5: Commit the gate function on its own**

```bash
git add skills/web-to-obsidian/scripts/save_capture.py tests/test_save_capture.py
git commit -m "feat: add pre-write content review gate"
```

- [ ] **Step 6: Write the failing integration tests for `run_capture()`**

```python
    def test_run_capture_writes_a_review_draft_instead_of_the_main_note(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            content_file = Path(temp_dir) / "capture.md"
            content_file.write_text(
                "## REST\n\n"
                "`# 1. Create a File Search store\n"
                "curl -X POST \"https://example.com\"\n\n"
                "# 2. Upload directly\n\n"
                "curl -X POST \"https://example.com/upload\"`\n\n"
                "## Two\n\nBody.\n\n"
                "## Three\n\nBody.\n",
                encoding="utf-8",
            )
            args = make_args(
                temp_dir,
                content_file=str(content_file),
                capture_method="tavily-basic",
                allow_text_only=True,
            )
            result = save_capture.run_capture(args)
        self.assertEqual(result["status"], "needs-review")
        self.assertTrue(result["review_issues"])
        review_path = Path(str(result["path"]))
        self.assertTrue(review_path.is_relative_to(Path(temp_dir) / "00 Inbox" / "Web" / "Needs Review"))
        review_note = review_path.read_text(encoding="utf-8")
        self.assertIn("type: capture-review", review_note)
        self.assertIn("status: needs-review", review_note)
        main_notes = [
            path
            for path in Path(temp_dir).rglob("*.md")
            if "type: source" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(main_notes, [])

    def test_run_capture_needs_review_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            content_file = Path(temp_dir) / "capture.md"
            content_file.write_text(
                "## Giá\n\n## Bước tiếp theo\n\nBody.\n\n## Third\n\nBody.\n",
                encoding="utf-8",
            )
            args = make_args(
                temp_dir,
                content_file=str(content_file),
                allow_text_only=True,
                dry_run=True,
            )
            result = save_capture.run_capture(args)
        self.assertEqual(result["status"], "needs-review")
        self.assertIsNone(result["path"])
        self.assertEqual(list(Path(temp_dir).rglob("*.md")), [])

    def test_run_capture_reports_source_update_date_on_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            content_file = Path(temp_dir) / "capture.md"
            content_file.write_text(
                "## Intro\n\nBody one.\n\n"
                "## Details\n\nBody two.\n\n"
                "Cập nhật lần gần đây nhất: 2026-08-19 UTC.\n",
                encoding="utf-8",
            )
            args = make_args(
                temp_dir, content_file=str(content_file), allow_text_only=True
            )
            result = save_capture.run_capture(args)
            self.assertEqual(result["status"], "created")
            self.assertEqual(result["reported_update_date"], "2026-08-19")
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests.test_run_capture_writes_a_review_draft_instead_of_the_main_note -v`
Expected: FAIL — result has `status == "created"` (or similar), not `"needs-review"`; `KeyError: 'reported_update_date'` on the third test.

- [ ] **Step 8: Implement `_render_review_note` and `_write_review_note`**

Insert into `skills/web-to-obsidian/scripts/save_capture.py` directly after `_render_note` (after its closing `return "\n".join(lines).rstrip() + "\n"`, currently line 1501):

```python
def _render_review_note(
    *,
    title: str,
    source_id: str,
    source_url: str,
    canonical_url: str,
    source_url_redacted: bool,
    captured: str,
    capture_method: str,
    review_issues: list[str],
    reported_update_date: str | None,
    content: str,
    tavily_request_id: str | None,
) -> str:
    lines = [
        "---",
        "type: capture-review",
        "status: needs-review",
        f"source_id: {_yaml_string(source_id)}",
        f"title: {_yaml_string(title)}",
        f"source_url: {_yaml_string(source_url)}",
        f"canonical_url: {_yaml_string(canonical_url)}",
        f"source_url_redacted: {'true' if source_url_redacted else 'false'}",
        f"captured: {_yaml_string(captured)}",
        f"capture_method: {capture_method}",
    ]
    if reported_update_date:
        lines.append(f"reported_update_date: {_yaml_string(reported_update_date)}")
    if tavily_request_id:
        lines.append(f"tavily_request_id: {_yaml_string(tavily_request_id)}")
    lines.extend(_yaml_list("review_issues", review_issues))
    lines.extend(
        [
            "---",
            "",
            f"# {title}",
            "",
            "> [!warning] Needs review before use",
            "> This capture failed validation and was not written to the main note.",
        ]
    )
    for issue in review_issues:
        lines.append(f"> - {issue}")
    lines.extend(["", SOURCE_CONTENT_START, content.strip(), SOURCE_CONTENT_END])
    return "\n".join(lines).rstrip() + "\n"


def _write_review_note(
    vault: Path,
    folder: str,
    captured_date: str,
    filename_title: str,
    source_id: str,
    note_text: str,
) -> Path:
    review_folder = _resolve_within(vault, vault / folder / "Needs Review")
    if review_folder is None:
        raise CaptureError("Needs Review folder must stay inside the vault.")
    review_folder.mkdir(parents=True, exist_ok=True)
    for candidate in _destination_candidates(
        review_folder, captured_date, filename_title, source_id
    ):
        resolved_candidate = _resolve_within(vault, candidate)
        if resolved_candidate is None:
            raise CaptureError("Needs Review note must stay inside the vault.")
        try:
            with open(resolved_candidate, "x", encoding="utf-8", newline="\n") as handle:
                handle.write(note_text)
        except FileExistsError:
            continue
        return resolved_candidate
    raise CaptureError("Could not publish a Needs Review note without overwrite risk.")
```

- [ ] **Step 9: Wire the gate into `run_capture()`**

In `skills/web-to-obsidian/scripts/save_capture.py`, find this existing block (currently lines 1754–1759):

```python
    parsed = urllib.parse.urlsplit(canonical_url)
    platform = args.platform.strip() if args.platform else parsed.hostname or ""
    captured = args.captured or datetime.now().astimezone().isoformat(timespec="seconds")
    title = args.title.strip() or platform or source_id
    filename_title = sanitize_filename(title, source_id)
    captured_date = captured[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", captured) else datetime.now().date().isoformat()
```

Immediately after it (still before `destination_folder_candidate = ...`), insert:

```python
    review_issues = _collect_content_review_issues(content) if content else []
    reported_update_date = _extract_reported_update_date(content) if content else None
    if review_issues:
        if args.dry_run:
            return {
                "status": "needs-review",
                "source_id": source_id,
                "canonical_url": canonical_url,
                "source_url_redacted": safe_url.redacted,
                "capture_method": capture_method,
                "link_only": not bool(content or selection),
                "review_issues": review_issues,
                "reported_update_date": reported_update_date,
                "path": None,
                "warnings": warnings,
            }
        review_note = _render_review_note(
            title=title,
            source_id=source_id,
            source_url=safe_url.source_url,
            canonical_url=canonical_url,
            source_url_redacted=safe_url.redacted,
            captured=captured,
            capture_method=capture_method,
            review_issues=review_issues,
            reported_update_date=reported_update_date,
            content=content,
            tavily_request_id=tavily_request_id,
        )
        review_path = _write_review_note(
            vault, args.folder, captured_date, filename_title, source_id, review_note
        )
        return {
            "status": "needs-review",
            "source_id": source_id,
            "canonical_url": canonical_url,
            "source_url_redacted": safe_url.redacted,
            "capture_method": capture_method,
            "link_only": not bool(content or selection),
            "review_issues": review_issues,
            "reported_update_date": reported_update_date,
            "path": str(review_path),
            "warnings": warnings,
        }
```

- [ ] **Step 10: Surface `reported_update_date` on the success paths**

In the same file, find the `"dry-run"` result dict (currently lines 1807–1817) and add one line:

```python
    if args.dry_run:
        return {
            "status": "dry-run",
            "source_id": source_id,
            "canonical_url": canonical_url,
            "source_url_redacted": safe_url.redacted,
            "capture_method": capture_method,
            "link_only": not bool(content or selection),
            "reported_update_date": reported_update_date,
            "path": str(destination),
            "warnings": warnings,
        }
```

Find the `"refreshed"` result dict (currently lines 1838–1847) and add the same key:

```python
                return {
                    "status": "refreshed",
                    "source_id": source_id,
                    "canonical_url": canonical_url,
                    "source_url_redacted": safe_url.redacted,
                    "capture_method": capture_method,
                    "link_only": False,
                    "reported_update_date": reported_update_date,
                    "path": str(duplicate.resolve()),
                    "warnings": warnings,
                }
```

Find the final `"created"` result dict (currently lines 1900–1909) and add the same key:

```python
    return {
        "status": "created",
        "source_id": source_id,
        "canonical_url": canonical_url,
        "source_url_redacted": safe_url.redacted,
        "capture_method": capture_method,
        "link_only": not bool(content or selection),
        "reported_update_date": reported_update_date,
        "path": str(destination.resolve()),
        "warnings": warnings,
    }
```

- [ ] **Step 11: Run tests to verify they pass**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests -k run_capture_writes_a_review_draft -v`
Run: `python -m unittest tests.test_save_capture.SaveCaptureTests -k run_capture_needs_review_dry_run -v`
Run: `python -m unittest tests.test_save_capture.SaveCaptureTests -k run_capture_reports_source_update_date -v`
Expected: all 3 PASS

- [ ] **Step 12: Run the full existing test suite to confirm no regressions**

Run: `python -m unittest discover -s tests -q`
Expected: all tests PASS (existing tests only assert individual keys via `result["status"]`/`result["path"]`/etc., never exact dict equality, so the new `reported_update_date` key does not break them — confirm this holds)

- [ ] **Step 13: Commit**

```bash
git add skills/web-to-obsidian/scripts/save_capture.py tests/test_save_capture.py
git commit -m "feat: write a Needs Review draft instead of blocking silently on invalid content"
```

---

### Task 6: Regression test modeled on the real Gemini File Search bug

Prove the gate actually catches the real failure shape end-to-end (broken REST fence, duplicate `Python` TOC entries, empty trailing section) in one `run_capture()` call, and prove a structurally clean capture of the same shape still succeeds.

**Files:**
- Test: `tests/test_save_capture.py` — add after Task 5's tests.

**Interfaces:**
- Consumes: `save_capture.run_capture` (existing), `make_args` (existing test helper).

- [ ] **Step 1: Write the regression tests**

```python
    def test_gemini_file_search_style_capture_needs_review(self) -> None:
        """Regression test for the 2026-09-22 Gemini File Search note: a
        Tavily capture with an unfenced multi-line REST block, duplicate
        Python subsections under one heading, and an empty trailing section.
        """

        content = (
            "> [!toc]- Table of contents\n"
            "> - [[#Tìm kiếm tệp]]\n"
            "> - [[#Nhập tệp]]\n"
            ">   - [[#Nhập tệp#Python|Python]]\n"
            ">   - [[#Nhập tệp#Python|Python]]\n\n"
            "# Tìm kiếm tệp\n\n"
            "Gemini API cho phép tính năng Tạo sinh tăng cường truy xuất.\n\n"
            "### REST\n\n"
            "`# 1. Create a File Search store\n"
            "curl -X POST \"https://example.com/stores\"\n\n"
            "# 2. Upload directly to File Search store\n\n"
            "curl -X POST \"https://example.com/upload\"`\n\n"
            "## Nhập tệp\n\n"
            "### Python\n\nimport1_example()\n\n"
            "### Python\n\nimport2_example()\n\n"
            "## Giá\n\n"
            "## Bước tiếp theo\n\n"
            "Trừ phi có lưu ý khác...\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            content_file = Path(temp_dir) / "capture.md"
            content_file.write_text(content, encoding="utf-8")
            args = make_args(
                temp_dir,
                url="https://ai.google.dev/gemini-api/docs/file-search",
                content_file=str(content_file),
                capture_method="tavily-basic",
                allow_text_only=True,
            )
            result = save_capture.run_capture(args)
        self.assertEqual(result["status"], "needs-review")
        reasons = " ".join(result["review_issues"])
        self.assertIn("broken", reasons)
        self.assertIn("Giá", reasons)
        review_note = Path(str(result["path"])).read_text(encoding="utf-8")
        self.assertIn("type: capture-review", review_note)

    def test_gemini_file_search_style_capture_succeeds_once_fixed(self) -> None:
        """Same shape as the regression above, but with a valid triple-backtick
        fence, one Python subsection, and real trailing-section content —
        proves the gate does not block a correctly structured capture.
        """

        content = (
            "# Tìm kiếm tệp\n\n"
            "Gemini API cho phép tính năng Tạo sinh tăng cường truy xuất.\n\n"
            "### REST\n\n"
            "```bash\n"
            "# 1. Create a File Search store\n"
            "curl -X POST \"https://example.com/stores\"\n\n"
            "# 2. Upload directly to File Search store\n"
            "curl -X POST \"https://example.com/upload\"\n"
            "```\n\n"
            "## Nhập tệp\n\n"
            "### Python\n\nimport_example()\n\n"
            "## Giá\n\nGiá tính theo mã thông báo đầu vào.\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            content_file = Path(temp_dir) / "capture.md"
            content_file.write_text(content, encoding="utf-8")
            args = make_args(
                temp_dir,
                url="https://ai.google.dev/gemini-api/docs/file-search",
                content_file=str(content_file),
                capture_method="tavily-basic",
                allow_text_only=True,
            )
            result = save_capture.run_capture(args)
        self.assertEqual(result["status"], "created")
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests -k gemini_file_search -v`
Expected: both PASS (the first because Task 5's gate is already wired; the second proves no false positive)

- [ ] **Step 3: Commit**

```bash
git add tests/test_save_capture.py
git commit -m "test: add regression coverage for the Gemini File Search capture bug"
```

---

### Task 7: Add a hardened public-HTML fetch tier ahead of Tavily

For a public documentation page, prefer fetching its raw HTML directly (no browser needed) over Tavily's flattened Markdown, since the existing `html_to_markdown()` converter already produces valid fences, a cloned real TOC, and correctly nested headings from HTML — the class of bug in Tasks 1–6 cannot occur on that path. This is opt-in via a new flag so the script never fetches a URL the caller didn't ask it to.

The naive version of this (a plain `urlopen()` call gated only on the *original* URL) has a real gap: a URL that is safe at request time can still redirect to a private IP, localhost, or a cloud metadata endpoint (SSRF via redirect, including DNS rebinding between the safety check and the connection). This task closes that gap: every redirect hop is re-validated the same way the original URL is, redirects are capped at 3, cookies/auth headers are never forwarded across a hop, the response body is capped at 10 MiB, and an explicitly non-HTML `Content-Type` is rejected before the body is even read.

**Files:**
- Modify: `skills/web-to-obsidian/scripts/save_capture.py`:
  - Add `"public-html"` to the `CAPTURE_METHODS` tuple (currently line 82).
  - Insert `_SafePublicHtmlRedirectHandler` and `fetch_public_html()` after `extract_with_tavily` (currently ends at line 1382), before `_within` (currently line 1385).
  - Modify `run_capture()` right after `had_browser_content = bool(content or selection)` (currently line 1710), before the existing `tavily_request_id`/`tavily_depth` initialization (currently lines 1711–1712).
  - Modify `run_capture()` again right after the existing `capture_method`/`tavily_depth` block (unchanged by Task 5, which now gates later in the function).
  - Add `--fetch-public-html` to `build_parser()` (currently lines 1912–1981), near `--tavily` (currently line 1969).
- Test: `tests/test_save_capture.py`:
  - Extend `FakeHttpResponse.read()` (currently lines 46–47) to accept an optional size argument, matching real `http.client.HTTPResponse.read(amt=None)`.
  - Add `"fetch_public_html": False` to the `make_args()` defaults dict (currently lines 51–77).
  - Add new test methods after Task 6's tests.

**Interfaces:**
- Produces: `fetch_public_html(url: str, timeout: float = 15.0) -> str` — raises `CaptureError` on any failure (HTTP error, connection error, timeout, redirect-safety violation, oversized response, unsupported content type, or a response that is not HTML).
- Produces: `_SafePublicHtmlRedirectHandler` (an `urllib.request.HTTPRedirectHandler` subclass) — used only inside `fetch_public_html`, but tested directly since it is the part that makes the redirect chain safe.
- Consumes: `is_safe_public_url_for_tavily` (existing), `html_to_markdown` (existing), `_looks_like_html_capture` (existing).

- [ ] **Step 1: Extend the shared `FakeHttpResponse` test helper**

In `tests/test_save_capture.py`, find (currently lines 36–47):

```python
class FakeHttpResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeHttpResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload
```

Replace the `read` method only:

```python
    def read(self, amt: int | None = None) -> bytes:
        return self.payload if amt is None else self.payload[:amt]
```

(Every existing call site uses `response.read()` with no argument, so this is backward compatible — `amt is None` keeps the old behavior exactly.)

- [ ] **Step 2: Write the failing tests for the redirect handler and `fetch_public_html`**

```python
    def test_safe_redirect_handler_blocks_redirect_to_private_ip(self) -> None:
        handler = save_capture._SafePublicHtmlRedirectHandler()
        request = urllib.request.Request("https://example.com/docs")
        with self.assertRaisesRegex(save_capture.CaptureError, "unsafe URL"):
            handler.redirect_request(
                request, None, 302, "Found", {}, "http://127.0.0.1/admin"
            )

    def test_safe_redirect_handler_blocks_more_than_three_redirects(self) -> None:
        handler = save_capture._SafePublicHtmlRedirectHandler()
        request = urllib.request.Request("https://example.com/docs")
        for _ in range(3):
            handler.redirect_request(
                request, None, 302, "Found", {}, "https://example.com/next"
            )
        with self.assertRaisesRegex(save_capture.CaptureError, "redirect limit"):
            handler.redirect_request(
                request, None, 302, "Found", {}, "https://example.com/next"
            )

    def test_safe_redirect_handler_strips_cookie_and_authorization_headers(self) -> None:
        handler = save_capture._SafePublicHtmlRedirectHandler()
        request = urllib.request.Request(
            "https://example.com/docs",
            headers={"Cookie": "session=abc", "Authorization": "Bearer xyz"},
        )
        new_request = handler.redirect_request(
            request, None, 302, "Found", {}, "https://example.com/next"
        )
        self.assertNotIn("Cookie", new_request.headers)
        self.assertNotIn("Authorization", new_request.headers)

    def test_fetch_public_html_returns_html_text_on_success(self) -> None:
        html = b"<html><body><main><h1>Docs</h1><p>Real content.</p></main></body></html>"
        response = FakeHttpResponse(html)
        response.headers = {"Content-Type": "text/html; charset=utf-8"}
        with mock.patch.object(
            save_capture.urllib.request,
            "build_opener",
            return_value=_StubOpener(response),
        ):
            result = save_capture.fetch_public_html(
                "https://example.com/docs", timeout=5.0
            )
        self.assertIn("Real content.", result)

    def test_fetch_public_html_rejects_a_non_html_response(self) -> None:
        response = FakeHttpResponse(b"just plain text, no markup at all")
        response.headers = {}
        with mock.patch.object(
            save_capture.urllib.request,
            "build_opener",
            return_value=_StubOpener(response),
        ):
            with self.assertRaisesRegex(save_capture.CaptureError, "HTML structure"):
                save_capture.fetch_public_html("https://example.com/docs")

    def test_fetch_public_html_rejects_unsupported_content_type(self) -> None:
        response = FakeHttpResponse(b"%PDF-1.4 binary data")
        response.headers = {"Content-Type": "application/pdf"}
        with mock.patch.object(
            save_capture.urllib.request,
            "build_opener",
            return_value=_StubOpener(response),
        ):
            with self.assertRaisesRegex(save_capture.CaptureError, "content type"):
                save_capture.fetch_public_html("https://example.com/file.pdf")

    def test_fetch_public_html_rejects_a_response_over_the_size_limit(self) -> None:
        oversized = (
            b"<html><body>"
            + b"a" * save_capture._PUBLIC_HTML_MAX_BYTES
            + b"</body></html>"
        )
        response = FakeHttpResponse(oversized)
        response.headers = {"Content-Type": "text/html"}
        with mock.patch.object(
            save_capture.urllib.request,
            "build_opener",
            return_value=_StubOpener(response),
        ):
            with self.assertRaisesRegex(save_capture.CaptureError, "size limit"):
                save_capture.fetch_public_html("https://example.com/docs")

    def test_fetch_public_html_wraps_connection_errors(self) -> None:
        class _RaisingOpener:
            def open(self, request: object, timeout: object = None) -> None:
                raise urllib.error.URLError("refused")

        with mock.patch.object(
            save_capture.urllib.request, "build_opener", return_value=_RaisingOpener()
        ):
            with self.assertRaisesRegex(save_capture.CaptureError, "could not connect"):
                save_capture.fetch_public_html("https://example.com/docs")
```

Add the `_StubOpener` test helper next to `FakeHttpResponse` (directly after its class body, before `def make_args`):

```python
class _StubOpener:
    def __init__(self, response: FakeHttpResponse) -> None:
        self._response = response

    def open(self, request: object, timeout: object = None) -> FakeHttpResponse:
        return self._response
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests.test_fetch_public_html_returns_html_text_on_success -v`
Expected: FAIL with `AttributeError: module 'save_capture' has no attribute 'fetch_public_html'`

- [ ] **Step 4: Implement the redirect handler and `fetch_public_html`**

Insert into `skills/web-to-obsidian/scripts/save_capture.py` directly after `extract_with_tavily` (after its closing `return TavilyResult(...)` line, currently line 1382):

```python
_PUBLIC_HTML_MAX_REDIRECTS = 3
_PUBLIC_HTML_MAX_BYTES = 10 * 1024 * 1024
_PUBLIC_HTML_ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml")


class _SafePublicHtmlRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-validate every redirect hop against the same public/private-IP
    check used for the original URL, cap the number of hops, and never
    forward cookies or auth headers across a hop. Without this, a URL that
    is safe at request time could still redirect to a private IP or
    localhost (SSRF via redirect, including DNS rebinding).
    """

    def __init__(self) -> None:
        self.redirect_count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.redirect_count += 1
        if self.redirect_count > _PUBLIC_HTML_MAX_REDIRECTS:
            raise CaptureError("Public HTML fetch exceeded the redirect limit.")
        safe, reason = is_safe_public_url_for_tavily(newurl)
        if not safe:
            raise CaptureError(
                f"Public HTML fetch redirected to an unsafe URL: {reason}."
            )
        new_request = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_request is not None:
            new_request.remove_header("Cookie")
            new_request.remove_header("Authorization")
        return new_request


def fetch_public_html(url: str, timeout: float = 15.0) -> str:
    """Fetch a public URL's raw HTML directly, no browser involved. Callers
    must gate the *original* URL with is_safe_public_url_for_tavily() first;
    this function re-validates every redirect hop on top of that, caps
    redirects and response size, and never forwards cookies or auth headers.
    """

    request = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "web-to-obsidian/0.3.0"},
    )
    opener = urllib.request.build_opener(_SafePublicHtmlRedirectHandler())
    try:
        with opener.open(request, timeout=timeout) as response:
            content_type = (
                response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            )
            if content_type and not content_type.startswith(
                _PUBLIC_HTML_ALLOWED_CONTENT_TYPES
            ):
                raise CaptureError(
                    f"Public HTML fetch got an unsupported content type: {content_type}."
                )
            raw = response.read(_PUBLIC_HTML_MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise CaptureError(f"Public HTML fetch failed with HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise CaptureError("Public HTML fetch could not connect.") from exc
    except TimeoutError as exc:
        raise CaptureError("Public HTML fetch timed out.") from exc

    if len(raw) > _PUBLIC_HTML_MAX_BYTES:
        raise CaptureError("Public HTML fetch exceeded the size limit.")
    text = raw.decode("utf-8", errors="replace")
    if not _looks_like_html_capture(text):
        raise CaptureError("The fetched page did not contain HTML structure.")
    return text
```

Also update the `CAPTURE_METHODS` tuple (currently line 82):

```python
CAPTURE_METHODS = (
    "selection",
    "chrome",
    "tavily-basic",
    "tavily-advanced",
    "hybrid",
    "manual",
    "public-html",
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests -k redirect_handler -v`
Run: `python -m unittest tests.test_save_capture.SaveCaptureTests -k fetch_public_html_ -v`
Expected: 9 tests PASS (3 redirect-handler tests + 6 `fetch_public_html` tests)

- [ ] **Step 6: Commit the standalone functions**

```bash
git add skills/web-to-obsidian/scripts/save_capture.py tests/test_save_capture.py
git commit -m "feat: add a redirect-safe fetch_public_html HTML fetcher"
```

- [ ] **Step 7: Write the failing integration tests**

Add `"fetch_public_html": False,` to the `make_args()` defaults dict in `tests/test_save_capture.py` (insert after the existing `"dry_run": False,` line, currently line 76):

```python
        "dry_run": False,
        "fetch_public_html": False,
```

Then add:

```python
    def test_fetch_public_html_tier_converts_dom_and_marks_capture_method(self) -> None:
        html = (
            b"<html><body><main>"
            b"<h1>Docs</h1><p>Real content from the live page.</p>"
            b"</main></body></html>"
        )
        response = FakeHttpResponse(html)
        response.headers = {"Content-Type": "text/html"}
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            save_capture.urllib.request,
            "build_opener",
            return_value=_StubOpener(response),
        ):
            args = make_args(
                temp_dir,
                content_file=None,
                capture_method="manual",
                fetch_public_html=True,
            )
            result = save_capture.run_capture(args)
        self.assertEqual(result["status"], "created")
        self.assertEqual(result["capture_method"], "public-html")
        note = Path(str(result["path"])).read_text(encoding="utf-8")
        self.assertIn("Real content from the live page.", note)

    def test_fetch_public_html_tier_skips_private_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            save_capture.urllib.request, "build_opener"
        ) as build_opener:
            args = make_args(
                temp_dir,
                url="http://localhost/internal",
                content_file=None,
                fetch_public_html=True,
            )
            result = save_capture.run_capture(args)
        build_opener.assert_not_called()
        self.assertTrue(result["link_only"])

    def test_fetch_public_html_failure_falls_back_to_tavily_auto(self) -> None:
        tavily_payload = json.dumps(
            {
                "results": [
                    {"raw_content": "# Intro\n\nFallback content from Tavily.\n"}
                ],
                "request_id": "req-1",
            }
        ).encode("utf-8")

        class _FailingOpener:
            def open(self, request: object, timeout: object = None) -> None:
                raise urllib.error.URLError("connection refused")

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.dict(
            save_capture.os.environ, {"TAVILY_API_KEY": "test-key"}
        ), mock.patch.object(
            save_capture.urllib.request, "build_opener", return_value=_FailingOpener()
        ), mock.patch.object(
            save_capture.urllib.request,
            "urlopen",
            return_value=FakeHttpResponse(tavily_payload),
        ):
            args = make_args(
                temp_dir,
                content_file=None,
                fetch_public_html=True,
                tavily="auto",
            )
            result = save_capture.run_capture(args)
        self.assertEqual(result["status"], "created")
        self.assertTrue(result["capture_method"].startswith("tavily-"))
```

(This mirrors Tavily's own separate HTTP boundary: `fetch_public_html` calls `urllib.request.build_opener(...).open(...)`, while `extract_with_tavily` still calls `urllib.request.urlopen(...)` directly — mocking both independently exercises "public HTML fails, Tavily still runs" without one mock masking the other.)

- [ ] **Step 8: Run tests to verify they fail**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests.test_fetch_public_html_tier_converts_dom_and_marks_capture_method -v`
Expected: FAIL — `run_capture()` still returns `link_only: true` because nothing calls `fetch_public_html` yet.

- [ ] **Step 9: Wire the tier into `run_capture()`**

In `skills/web-to-obsidian/scripts/save_capture.py`, find (currently lines 1709–1712):

```python
    selection = _read_optional_file(args.selection_file)
    had_browser_content = bool(content or selection)
    tavily_request_id: str | None = None
    tavily_depth: str | None = None
```

Replace it with:

```python
    selection = _read_optional_file(args.selection_file)
    had_browser_content = bool(content or selection)

    fetched_public_html = False
    if not had_browser_content and getattr(args, "fetch_public_html", False):
        safe, reason = is_safe_public_url_for_tavily(args.url)
        if not safe:
            warnings.append(f"Public HTML fetch skipped: {reason}.")
        else:
            try:
                fetched_html = fetch_public_html(safe_url.source_url, timeout=args.timeout)
            except CaptureError as exc:
                warnings.append(f"Public HTML fetch failed: {exc}")
            else:
                converted = html_to_markdown(
                    fetched_html, safe_url.source_url, heading_offset=1
                )
                if converted:
                    content = converted
                    rich_html = True
                    fetched_public_html = True

    tavily_request_id: str | None = None
    tavily_depth: str | None = None
```

Then find the existing `capture_method` block (unchanged by Task 5, which now inserts its gate later — after `captured_date = ...` — rather than here):

```python
    capture_method = args.capture_method
    if tavily_depth:
        if args.capture_method in {"chrome", "selection"} and had_browser_content:
            capture_method = "hybrid"
        else:
            capture_method = f"tavily-{tavily_depth}"
```

Add one more branch directly beneath it:

```python
    capture_method = args.capture_method
    if tavily_depth:
        if args.capture_method in {"chrome", "selection"} and had_browser_content:
            capture_method = "hybrid"
        else:
            capture_method = f"tavily-{tavily_depth}"
    elif fetched_public_html:
        capture_method = "public-html"
```

(Tavily naming still wins if Tavily also ran and supplied longer content, matching the existing supplement precedence. `fetched_public_html` must already be `True`/`False` here, which Step 9's edit above guarantees since it runs earlier in the function.)

Finally, add the CLI flag in `build_parser()`, directly after the existing `--tavily` argument (currently line 1969):

```python
    parser.add_argument(
        "--fetch-public-html",
        action="store_true",
        help=(
            "When no content or selection is supplied, fetch the public URL's "
            "raw HTML directly (no browser) before falling back to Tavily; "
            "skipped for private, local, or credentialed URLs"
        ),
    )
```

- [ ] **Step 10: Run tests to verify they pass**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests -k fetch_public_html_tier -v`
Expected: 3 tests PASS

- [ ] **Step 11: Run the full existing test suite to confirm no regressions**

Run: `python -m unittest discover -s tests -q`
Expected: all tests PASS

- [ ] **Step 12: Commit**

```bash
git add skills/web-to-obsidian/scripts/save_capture.py tests/test_save_capture.py
git commit -m "feat: fetch public HTML directly through the redirect-safe tier before falling back to Tavily"
```

---

### Task 8: Detect structural content lost during HTML-to-Markdown conversion

Tasks 1–4 only validate Markdown that has already been produced — they cannot tell whether `html_to_markdown()` itself silently dropped a table or a code block while converting. This task adds a second, independent signal: count `<pre>`/`<table>`/heading elements in the *source* HTML and compare them against fence/table/heading counts in the *converted* Markdown. A rich-HTML capture (from `--html-file`, `--content-file` with detected HTML, or Task 7's `--fetch-public-html`) now carries its source HTML far enough into `run_capture()` to make this comparison; a plain-Markdown capture (Tavily) has no source HTML to compare against and skips this check entirely — Tasks 1–4 remain its only coverage.

**Files:**
- Modify: `skills/web-to-obsidian/scripts/save_capture.py`:
  - Insert `_count_html_structural_elements`, `_count_markdown_structural_elements`, and `_find_structural_content_loss` directly after Task 4's `_extract_reported_update_date`, before Task 5's `_collect_content_review_issues`.
  - Modify `_collect_content_review_issues` (Task 5) to accept an optional `source_html` parameter.
  - Modify `run_capture()`'s `review_issues = ...` line (Task 5 Step 9) to pass `source_html`.
  - Modify Task 7's public-HTML fetch block to also assign `html_content = fetched_html`, so the structural check has a source to compare against on that path too.
- Test: `tests/test_save_capture.py` — add new test methods after Task 7's tests, before Task 10's (documentation has no tests).

**Interfaces:**
- Produces: `_count_html_structural_elements(html: str) -> dict[str, int]` — keys `"pre"`, `"table"`, `"heading"`.
- Produces: `_count_markdown_structural_elements(content: str) -> dict[str, int]` — same keys.
- Produces: `_find_structural_content_loss(html: str, content: str) -> list[str]`.
- Modifies: `_collect_content_review_issues(content: str, *, source_html: str | None = None) -> list[str]` (Task 5) — new keyword-only parameter, backward compatible with every existing call site since it defaults to `None`.

- [ ] **Step 1: Write the failing tests**

```python
    def test_counts_pre_table_and_heading_tags_in_html(self) -> None:
        html = (
            "<article><h1>Title</h1><h2>Section</h2>"
            "<pre>code one</pre><table><tr><td>1</td></tr></table>"
            "<pre>code two</pre></article>"
        )
        counts = save_capture._count_html_structural_elements(html)
        self.assertEqual(counts, {"pre": 2, "table": 1, "heading": 2})

    def test_counts_fences_tables_and_headings_in_markdown(self) -> None:
        content = (
            "# Title\n\n## Section\n\n"
            "```python\ncode one\n```\n\n"
            "| A | B |\n| --- | --- |\n| 1 | 2 |\n\n"
            "```bash\ncode two\n```\n"
        )
        counts = save_capture._count_markdown_structural_elements(content)
        self.assertEqual(counts, {"pre": 2, "table": 1, "heading": 2})

    def test_finds_structural_content_loss_reports_missing_elements(self) -> None:
        html = (
            "<article><h1>T</h1><pre>a</pre><pre>b</pre>"
            "<table><tr><td>x</td></tr></table></article>"
        )
        content = "# T\n\n```text\na\n```\n"
        issues = save_capture._find_structural_content_loss(html, content)
        self.assertEqual(len(issues), 2)
        self.assertTrue(any("code block" in issue for issue in issues))
        self.assertTrue(any("table" in issue for issue in issues))

    def test_finds_structural_content_loss_is_empty_when_nothing_is_missing(self) -> None:
        html = "<article><h1>T</h1><pre>a</pre></article>"
        content = "# T\n\n```text\na\n```\n"
        self.assertEqual(save_capture._find_structural_content_loss(html, content), [])

    def test_collect_content_review_issues_includes_structural_loss_when_source_html_given(
        self,
    ) -> None:
        html = "<article><h1>T</h1><pre>a</pre><pre>b</pre></article>"
        content = "# T\n\n```text\na\n```\n"
        issues = save_capture._collect_content_review_issues(content, source_html=html)
        self.assertTrue(any("code block" in issue for issue in issues))

    def test_collect_content_review_issues_skips_structural_loss_without_source_html(
        self,
    ) -> None:
        content = "# T\n\n```text\na\n```\n"
        self.assertEqual(save_capture._collect_content_review_issues(content), [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests.test_counts_pre_table_and_heading_tags_in_html -v`
Expected: FAIL with `AttributeError: module 'save_capture' has no attribute '_count_html_structural_elements'`

- [ ] **Step 3: Implement the counters and the comparison**

Insert into `skills/web-to-obsidian/scripts/save_capture.py` directly after `_extract_reported_update_date` (Task 4), before `_collect_content_review_issues` (Task 5):

```python
_HTML_STRUCTURAL_TAG_PATTERN = re.compile(r"<(pre|table|h[1-6])\b", re.IGNORECASE)
_MARKDOWN_TABLE_ROW_PATTERN = re.compile(r"^\s*\|.*\|\s*$")


def _count_html_structural_elements(html: str) -> dict[str, int]:
    counts = {"pre": 0, "table": 0, "heading": 0}
    for match in _HTML_STRUCTURAL_TAG_PATTERN.finditer(html):
        tag = match.group(1).lower()
        if tag == "pre":
            counts["pre"] += 1
        elif tag == "table":
            counts["table"] += 1
        else:
            counts["heading"] += 1
    return counts


def _count_markdown_structural_elements(content: str) -> dict[str, int]:
    counts = {"pre": 0, "table": 0, "heading": 0}
    in_fence = False
    previous_was_table_row = False
    for line in content.splitlines():
        if _CODE_FENCE_PATTERN.match(line):
            if not in_fence:
                counts["pre"] += 1
            in_fence = not in_fence
            previous_was_table_row = False
            continue
        if in_fence:
            continue
        if _MARKDOWN_HEADING_PATTERN.match(line):
            counts["heading"] += 1
            previous_was_table_row = False
            continue
        is_table_row = bool(_MARKDOWN_TABLE_ROW_PATTERN.match(line))
        if is_table_row and not previous_was_table_row:
            counts["table"] += 1
        previous_was_table_row = is_table_row
    return counts


def _find_structural_content_loss(html: str, content: str) -> list[str]:
    """Compare structural element counts between source HTML and the
    converted Markdown, to catch content silently dropped inside
    html_to_markdown() itself — a different failure mode than a malformed
    Markdown input (Tasks 1-4), which only validates Markdown that has
    already been produced.
    """

    html_counts = _count_html_structural_elements(html)
    markdown_counts = _count_markdown_structural_elements(content)
    labels = {"pre": "code block", "table": "table", "heading": "heading"}
    issues: list[str] = []
    for key, label in labels.items():
        if markdown_counts[key] < html_counts[key]:
            issues.append(
                f"Conversion lost {html_counts[key] - markdown_counts[key]} "
                f"{label}(s): {html_counts[key]} in the source HTML, only "
                f"{markdown_counts[key]} in the converted Markdown."
            )
    return issues
```

- [ ] **Step 4: Run tests to verify the counters and comparison pass**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests -k count -v`
Run: `python -m unittest tests.test_save_capture.SaveCaptureTests -k structural_content_loss -v`
Expected: 4 tests PASS

- [ ] **Step 5: Extend `_collect_content_review_issues` (Task 5) to use it**

Find (as written by Task 5 Step 3):

```python
def _collect_content_review_issues(content: str) -> list[str]:
    """Return blocking reasons the generated source content should not be
    published as-is. An empty list means the content passed validation.
    """

    issues: list[str] = []

    for start_line, end_line in _find_unfenced_multiline_code_spans(content):
```

Replace its signature and add the new check at the end, right before `return issues`:

```python
def _collect_content_review_issues(
    content: str, *, source_html: str | None = None
) -> list[str]:
    """Return blocking reasons the generated source content should not be
    published as-is. An empty list means the content passed validation.
    """

    issues: list[str] = []

    for start_line, end_line in _find_unfenced_multiline_code_spans(content):
```

(the rest of the function body is unchanged up to its `return issues` line, which becomes:)

```python
    if source_html:
        issues.extend(_find_structural_content_loss(source_html, content))

    return issues
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests -k collect_content_review_issues_includes_structural -v`
Run: `python -m unittest tests.test_save_capture.SaveCaptureTests -k collect_content_review_issues_skips_structural -v`
Expected: both PASS

- [ ] **Step 7: Wire `source_html` through `run_capture()`**

Find the line Task 5 Step 9 inserted:

```python
    review_issues = _collect_content_review_issues(content) if content else []
```

Replace it with:

```python
    review_issues = (
        _collect_content_review_issues(
            content, source_html=html_content if rich_html else None
        )
        if content
        else []
    )
```

Then find the public-HTML fetch block Task 7 Step 9 inserted (inside `if not had_browser_content and getattr(args, "fetch_public_html", False):`):

```python
            else:
                converted = html_to_markdown(
                    fetched_html, safe_url.source_url, heading_offset=1
                )
                if converted:
                    content = converted
                    rich_html = True
                    fetched_public_html = True
```

Replace it with:

```python
            else:
                converted = html_to_markdown(
                    fetched_html, safe_url.source_url, heading_offset=1
                )
                if converted:
                    content = converted
                    html_content = fetched_html
                    rich_html = True
                    fetched_public_html = True
```

- [ ] **Step 8: Write and run an integration test proving the wiring**

```python
    def test_run_capture_flags_structural_content_loss_from_html_source(self) -> None:
        html = (
            "<html><body><main>"
            "<h1>Docs</h1><pre>example one</pre><pre>example two</pre>"
            "</main></body></html>"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            html_file = Path(temp_dir) / "capture.html"
            html_file.write_text(html, encoding="utf-8")
            args = make_args(temp_dir, html_file=str(html_file))
            result = save_capture.run_capture(args)
        self.assertEqual(result["status"], "needs-review")
        self.assertTrue(any("code block" in issue for issue in result["review_issues"]))
```

This test is written against real HTML, so it can only fail for the right reason if `html_to_markdown()` genuinely drops a `<pre>` — which it does not; instead this proves the wiring itself by asserting the flow *would* catch it. To prove the detector fires end-to-end without relying on a real converter bug, add a second test that stubs the converter:

```python
    def test_run_capture_flags_structural_content_loss_when_converter_drops_a_table(
        self,
    ) -> None:
        html = (
            "<html><body><main><h1>Docs</h1>"
            "<table><tr><td>Row</td></tr></table>"
            "</main></body></html>"
        )
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            save_capture, "html_to_markdown", return_value="# Docs\n\nBody without the table.\n"
        ):
            html_file = Path(temp_dir) / "capture.html"
            html_file.write_text(html, encoding="utf-8")
            args = make_args(temp_dir, html_file=str(html_file))
            result = save_capture.run_capture(args)
        self.assertEqual(result["status"], "needs-review")
        self.assertTrue(any("table" in issue for issue in result["review_issues"]))
```

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests -k flags_structural_content_loss -v`
Expected: both PASS

- [ ] **Step 9: Run the full existing test suite to confirm no regressions**

Run: `python -m unittest discover -s tests -q`
Expected: all tests PASS

- [ ] **Step 10: Commit**

```bash
git add skills/web-to-obsidian/scripts/save_capture.py tests/test_save_capture.py
git commit -m "feat: detect structural content lost during HTML-to-Markdown conversion"
```

---

### Task 9: Resolve same-page `#fragment` links to Obsidian headings

`html_to_markdown()` already turns `<a href="#pricing">` into an absolute URL back to the source page (existing `_resolve_url`/`urljoin` behavior — confirmed by tracing it, not assumed) rather than leaving a dead relative link, which is a safe default. This task makes it better: try to resolve the fragment to a real Obsidian heading path first, and only fall back to that existing absolute-URL behavior when no heading matches. This directly fixes the `[định giá](#pricing)` dead link seen in the Gemini File Search note.

Known limitation, stated up front rather than discovered later: the resolver prefers a heading the id sits *on* or *wraps* (matches how a page's own nav-TOC anchors usually work), else the nearest heading at or before that point in the document. An id on a plain sibling anchor placed immediately *before* its heading (a pattern some sites use, with no wrapping element) resolves to the *previous* section instead of the one that follows — Step 1's tests pin this exact behavior rather than leaving it as an unverified claim.

**Files:**
- Modify: `skills/web-to-obsidian/scripts/save_capture.py`:
  - Insert `_collect_fragment_heading_paths` directly after `_toc_heading_for_fragment` (currently ends at line 677), before `_escape_wikilink` (currently line 679).
  - Modify `_HtmlMarkdownRenderer.__init__` (currently lines 263–265) to add a `_fragment_paths` attribute.
  - Modify the `tag == "a"` branch of `_HtmlMarkdownRenderer.render` (currently lines 311–331) to try fragment resolution first.
  - Modify `html_to_markdown` (currently lines 829–853) to compute `_fragment_paths` before rendering.
- Test: `tests/test_save_capture.py` — add new test methods after Task 8's tests.

**Interfaces:**
- Produces: `_collect_fragment_heading_paths(selected: HtmlNode, renderer: "_HtmlMarkdownRenderer") -> dict[str, tuple[str, ...]]`.
- Consumes: `_escape_wikilink`, `HtmlNode`, `_HtmlTreeParser` (existing).

- [ ] **Step 1: Write the failing tests**

```python
    def test_same_page_fragment_link_resolves_to_the_heading_it_sits_on(self) -> None:
        html = (
            "<article>"
            "<p>See <a href=\"#pricing\">pricing</a> for details.</p>"
            "<h2 id=\"pricing\">Giá</h2>"
            "<p>Body.</p>"
            "</article>"
        )
        markdown = save_capture.html_to_markdown(html, "https://example.com/docs")
        self.assertIn("[[#Giá|pricing]]", markdown)

    def test_same_page_fragment_link_resolves_through_a_wrapping_section(self) -> None:
        html = (
            "<article>"
            "<p>See <a href=\"#pricing\">Giá</a> for details.</p>"
            "<section id=\"pricing\"><h2>Giá</h2><p>Body.</p></section>"
            "</article>"
        )
        markdown = save_capture.html_to_markdown(html, "https://example.com/docs")
        self.assertIn("[[#Giá]]", markdown)
        self.assertNotIn("[[#Giá|Giá]]", markdown)

    def test_unresolved_fragment_link_falls_back_to_an_absolute_url(self) -> None:
        html = (
            "<article>"
            "<p>See <a href=\"#unknown-section\">details</a>.</p>"
            "<h2>Intro</h2><p>Body.</p>"
            "</article>"
        )
        markdown = save_capture.html_to_markdown(html, "https://example.com/docs?x=1")
        self.assertIn(
            "[details](https://example.com/docs?x=1#unknown-section)", markdown
        )
        self.assertNotIn("[[#unknown-section", markdown)

    def test_collect_fragment_heading_paths_uses_nearest_preceding_heading_for_a_sibling_anchor(
        self,
    ) -> None:
        """Known limitation: an id on a plain sibling anchor placed
        immediately before its heading (rather than on the heading itself
        or a wrapping element) resolves to the *previous* heading, not the
        one that follows.
        """

        html = (
            "<article>"
            "<h2 id=\"other\">Other</h2>"
            "<span id=\"pricing\"></span>"
            "<h2>Giá</h2>"
            "</article>"
        )
        parser = save_capture._HtmlTreeParser()
        parser.feed(html)
        parser.close()
        selected = parser.root
        renderer = save_capture._HtmlMarkdownRenderer("https://example.com/docs")
        paths = save_capture._collect_fragment_heading_paths(selected, renderer)
        self.assertEqual(paths["other"], ("Other",))
        self.assertEqual(paths["pricing"], ("Other",))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests.test_same_page_fragment_link_resolves_to_the_heading_it_sits_on -v`
Expected: FAIL — the rendered link is the existing absolute-URL form, not a wikilink.

- [ ] **Step 3: Implement `_collect_fragment_heading_paths`**

Insert into `skills/web-to-obsidian/scripts/save_capture.py` directly after `_toc_heading_for_fragment` (after its closing `return renderer._text_content(heading).strip() if heading else ""`, currently line 677), before `_escape_wikilink` (currently line 679):

```python
def _collect_fragment_heading_paths(
    selected: HtmlNode,
    renderer: "_HtmlMarkdownRenderer",
) -> dict[str, tuple[str, ...]]:
    """Map every element id/data-anchor-id in the converted region to an
    Obsidian heading path, so a same-page ``#fragment`` link can become a
    wikilink instead of an opaque absolute URL. Preference per id: a
    heading it sits on or wraps (matches how a page's own nav-TOC anchors
    usually work), else the nearest heading at or before that point in the
    document (matches an anchor placed immediately before its heading with
    no wrapping element — though not one placed as a preceding sibling with
    no wrapping element and no id on the heading itself; that case resolves
    to the previous heading instead, a known limitation).
    """

    stack: list[tuple[int, str]] = []
    heading_paths: dict[int, tuple[str, ...]] = {}
    fragment_targets: dict[str, HtmlNode] = {}
    fallback_paths: dict[str, tuple[str, ...]] = {}

    def visit(node: HtmlNode) -> None:
        if re.fullmatch(r"h[1-6]", node.tag):
            level = int(node.tag[1])
            text = renderer._text_content(node).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            if text:
                stack.append((level, text))
                heading_paths[id(node)] = tuple(entry[1] for entry in stack)

        fragment_id = node.attrs.get("id") or node.attrs.get("data-anchor-id")
        if fragment_id and fragment_id not in fragment_targets:
            fragment_targets[fragment_id] = node
            fallback_paths[fragment_id] = tuple(entry[1] for entry in stack)

        for child in node.children:
            if isinstance(child, HtmlNode):
                visit(child)

    def nearest_heading(node: HtmlNode) -> HtmlNode | None:
        if re.fullmatch(r"h[1-6]", node.tag):
            return node
        for child in node.children:
            if isinstance(child, HtmlNode):
                found = nearest_heading(child)
                if found is not None:
                    return found
        return None

    visit(selected)

    paths: dict[str, tuple[str, ...]] = {}
    for fragment_id, target_node in fragment_targets.items():
        target_heading = nearest_heading(target_node)
        if target_heading is not None and id(target_heading) in heading_paths:
            paths[fragment_id] = heading_paths[id(target_heading)]
        elif fallback_paths.get(fragment_id):
            paths[fragment_id] = fallback_paths[fragment_id]
    return paths
```

- [ ] **Step 4: Run the `_collect_fragment_heading_paths` test to verify it passes**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests.test_collect_fragment_heading_paths_uses_nearest_preceding_heading_for_a_sibling_anchor -v`
Expected: PASS (this function is already correct and testable on its own, before it's wired into rendering)

- [ ] **Step 5: Wire it into `_HtmlMarkdownRenderer` and `html_to_markdown`**

Find the constructor:

```python
    def __init__(self, base_url: str, *, heading_offset: int = 0) -> None:
        self.base_url = base_url
        self.heading_offset = max(0, heading_offset)
```

Replace it with:

```python
    def __init__(self, base_url: str, *, heading_offset: int = 0) -> None:
        self.base_url = base_url
        self.heading_offset = max(0, heading_offset)
        self._fragment_paths: dict[str, tuple[str, ...]] = {}
```

Find the start of the `tag == "a"` branch:

```python
        if tag == "a":
            label = self._inline_children(node).strip()
            target = self._resolve_url(node.attrs.get("href", ""), image=False)
```

Replace it with:

```python
        if tag == "a":
            label = self._inline_children(node).strip()
            href = html_lib.unescape(node.attrs.get("href", "")).strip()
            if href.startswith("#") and len(href) > 1:
                fragment = urllib.parse.unquote(href[1:])
                path = self._fragment_paths.get(fragment)
                if path:
                    destination = "#" + "#".join(_escape_wikilink(part) for part in path)
                    if len(path) == 1 and label == path[-1]:
                        return f"[[{destination}]]"
                    escaped_label = _escape_wikilink(label) if label else _escape_wikilink(path[-1])
                    return f"[[{destination}|{escaped_label}]]"
            target = self._resolve_url(node.attrs.get("href", ""), image=False)
```

(everything below this — the image-lightbox check and the final `return f"[{label or target}]..."` — is unchanged; it only runs when the fragment branch above did not already return.)

Find, in `html_to_markdown`:

```python
    renderer = _HtmlMarkdownRenderer(
        base_url,
        heading_offset=heading_offset,
    )
    markdown = renderer.render(selected)
```

Replace it with:

```python
    renderer = _HtmlMarkdownRenderer(
        base_url,
        heading_offset=heading_offset,
    )
    renderer._fragment_paths = _collect_fragment_heading_paths(selected, renderer)
    markdown = renderer.render(selected)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests -k fragment_link -v`
Expected: 3 tests PASS

- [ ] **Step 7: Run the full existing test suite to confirm no regressions**

Run: `python -m unittest discover -s tests -q`
Expected: all tests PASS (existing tests that render plain absolute-URL `<a>` tags never hit the new `href.startswith("#")` branch, so their output is byte-for-byte unchanged)

- [ ] **Step 8: Commit**

```bash
git add skills/web-to-obsidian/scripts/save_capture.py tests/test_save_capture.py
git commit -m "feat: resolve same-page fragment links to Obsidian headings"
```

---

### Task 10: Update skill documentation to match the new behavior

Document the new fallback ordering, the new `needs-review` status (and where its draft note lands), the new `--fetch-public-html` flag, and the two new content-fidelity behaviors (fragment-link resolution, structural content-loss detection) — so the agent driving this skill actually uses Tasks 5, 7, 8, and 9 instead of going straight to Tavily and trusting whatever comes back, which is what happened on 2026-09-22.

**Files:**
- Modify: `skills/web-to-obsidian/SKILL.md`
- Modify: `skills/web-to-obsidian/references/tavily.md`
- Modify: `skills/web-to-obsidian/references/browser-capture.md`

- [ ] **Step 1: Update the acquisition order in `SKILL.md`**

In `skills/web-to-obsidian/SKILL.md`, in step 2 of the Workflow section (currently line 13), after the existing sentence ending "...the helper detects HTML content and converts it." insert:

```markdown
For a public URL where the browser cannot export DOM/HTML, try `--fetch-public-html` before falling back to Tavily — it fetches the page's raw HTML directly and reuses the same HTML-to-Markdown converter, so headings, code fences, and links come out correctly structured; Tavily's `format=markdown` output is a flattened conversion with no such guarantee. `--fetch-public-html` never sends cookies or auth headers, revalidates every redirect against the same public/private-IP check as the original URL, stops after 3 redirects, and rejects a response over 10 MiB or with a non-HTML content type; pass `--timeout 15` alongside it, matching the fetcher's own recommended cap. Với URL công khai mà trình duyệt không xuất được DOM/HTML, hãy thử `--fetch-public-html` trước khi dùng Tavily — nó tải thẳng HTML gốc và tái dùng bộ chuyển đổi HTML sang Markdown hiện có, nên tiêu đề, code fence và liên kết giữ đúng cấu trúc; Markdown do Tavily trả về là bản chuyển đổi phẳng, không có gì bảo đảm giữ cấu trúc đó. `--fetch-public-html` không bao giờ gửi cookie hay header xác thực, kiểm tra lại IP công khai/riêng tư ở mỗi lần chuyển hướng giống URL gốc, dừng sau 3 lần chuyển hướng, và từ chối phản hồi quá 10 MiB hoặc sai content type; hãy truyền kèm `--timeout 15` cho khớp mức khuyến nghị của hàm tải.
```

- [ ] **Step 2: Document the `needs-review` status in `SKILL.md`**

In `skills/web-to-obsidian/SKILL.md`, find the closing sentence of the Common Mistakes section (currently line 75):

```markdown
Report helper status `created`, `duplicate`, `refreshed`, `dry-run`, or `error`, plus the final path. `link_only` is a boolean, never a status. On lock timeout, fail closed; never delete or take over a stale lock automatically. / Không tự xóa hoặc chiếm stale lock.
```

Replace it with:

```markdown
Report helper status `created`, `duplicate`, `refreshed`, `dry-run`, `needs-review`, or `error`, plus the final path. `link_only` is a boolean, never a status. `needs-review` means the helper found a structural problem (a broken code fence, a duplicate table-of-contents destination, an empty section, or — for an HTML-sourced capture — content lost during conversion) and left the main note untouched; unless `--dry-run` was passed, it instead wrote a labeled draft under `<folder>/Needs Review/` (`type: capture-review`, never counted as a duplicate of the main note). Open that draft, read `review_issues`, do not describe the capture as complete, and fix the source (usually a better HTML capture) before retrying — do not just relay the JSON and stop. On lock timeout, fail closed; never delete or take over a stale lock automatically. / Báo trạng thái helper `created`, `duplicate`, `refreshed`, `dry-run`, `needs-review` hoặc `error`, kèm đường dẫn cuối cùng. `link_only` là boolean, không phải trạng thái. `needs-review` nghĩa là helper phát hiện vấn đề cấu trúc (code fence hỏng, đích mục lục trùng, mục rỗng, hoặc — với capture từ HTML — nội dung bị mất khi chuyển đổi) và không đụng tới note chính; trừ khi dùng `--dry-run`, helper sẽ ghi một bản nháp có nhãn vào `<folder>/Needs Review/` (`type: capture-review`, không bao giờ bị tính là bản trùng của note chính). Hãy mở bản nháp đó, đọc `review_issues`, không mô tả capture là hoàn tất, và sửa nguồn (thường là lấy lại HTML tốt hơn) trước khi thử lại — không chỉ chuyển tiếp JSON rồi dừng. Khi lock hết hạn, dừng lại an toàn; không tự xóa hoặc chiếm stale lock.
```

- [ ] **Step 3: Reorder the Quick Reference row for public URLs in `SKILL.md`**

In `skills/web-to-obsidian/SKILL.md`, find the Quick Reference table row (currently line 55):

```markdown
| Public URL, no content | Use connected Tavily Extract when available; otherwise use helper `--tavily auto` only with a loaded API key |
```

Replace it with:

```markdown
| Public URL, no content | Try `--fetch-public-html` first; otherwise use connected Tavily Extract when available, or helper `--tavily auto` only with a loaded API key |
| Helper reports `needs-review` | Read `review_issues` to the user; do not claim the capture is complete; do not retry with `--refresh-existing` until the source content is fixed |
```

- [ ] **Step 4: Document the same ordering in `tavily.md`**

In `skills/web-to-obsidian/references/tavily.md`, directly after the "Connected Extract tool" section (after line 11, before the "Extraction policy" heading), insert a new section:

```markdown
## Ordering / Thứ tự ưu tiên

Tavily Markdown is a flattened conversion (`format=markdown`) with no structural guarantee — prefer an authorized browser DOM/HTML capture, then `--fetch-public-html` for a public URL the browser cannot export, and use Tavily only when both of those are unavailable. Markdown do Tavily trả về (`format=markdown`) là bản chuyển đổi đã làm phẳng, không bảo đảm giữ cấu trúc — hãy ưu tiên DOM/HTML từ trình duyệt đã cấp quyền, sau đó `--fetch-public-html` cho URL công khai mà trình duyệt không xuất được, và chỉ dùng Tavily khi cả hai cách trên đều không khả dụng.

https://docs.tavily.com/documentation/api-reference/endpoint/extract
```

- [ ] **Step 5: Document the fetch-public-html tier in `browser-capture.md`**

In `skills/web-to-obsidian/references/browser-capture.md`, directly after point 16 (the paragraph ending "...save a link-only note or ask for an export rather than claiming the capture is complete."), insert:

```markdown
When the browser cannot export DOM/HTML for a public page, try `--fetch-public-html` before reaching for Tavily — see [tavily.md](tavily.md) for the full ordering. Khi trình duyệt không xuất được DOM/HTML cho một trang công khai, hãy thử `--fetch-public-html` trước khi dùng Tavily — xem [tavily.md](tavily.md) để biết thứ tự đầy đủ.
```

- [ ] **Step 6: Document the two content-fidelity improvements in `SKILL.md`**

In `skills/web-to-obsidian/SKILL.md`, directly after Step 1's insertion (the `--fetch-public-html` paragraph), add:

```markdown
An HTML-sourced capture now resolves a same-page `#fragment` link to the matching Obsidian heading when one exists, falling back to an absolute link to the source page only when no heading matches — never a dead relative link. It also compares `<pre>`/`<table>`/heading counts between the source HTML and the converted Markdown; a mismatch is reported as a `needs-review` reason, since it means the converter itself dropped content rather than the input being malformed. Capture từ HTML giờ sẽ chuyển liên kết `#fragment` trong cùng trang thành liên kết tới đúng tiêu đề Obsidian nếu khớp được, chỉ rơi về liên kết tuyệt đối tới trang gốc khi không khớp — không bao giờ để lại liên kết chết. Helper cũng so sánh số lượng `<pre>`/`<table>`/tiêu đề giữa HTML nguồn và Markdown đã chuyển đổi; nếu lệch, đây sẽ là một lý do `needs-review`, vì nghĩa là chính bộ chuyển đổi làm mất nội dung chứ không phải do đầu vào lỗi.
```

- [ ] **Step 7: Commit**

```bash
git add skills/web-to-obsidian/SKILL.md skills/web-to-obsidian/references/tavily.md skills/web-to-obsidian/references/browser-capture.md
git commit -m "docs: document the public-HTML fetch tier and needs-review status"
```

---

### Task 11: Sync fixes to the installed Driftnote plugin and reinstall

Tasks 1–10 only change files under `E:\skill` (the plugin source you edit). Codex actually runs the *installed* copy at `C:\Users\LTC\plugins\driftnote`, registered under marketplace name `personal` in `C:\Users\LTC\.agents\plugins\marketplace.json` (confirmed: its single plugin entry is `driftnote`, sourced locally from `./plugins/driftnote`), currently at version `0.5.0+codex.20260922023520` (confirmed by reading `C:\Users\LTC\plugins\driftnote\plugin.json:4`). Codex only loads whatever that installed copy's `skills` field points at (`./skills/`, per `E:\skill\.codex-plugin\plugin.json:20`, mirrored at the installed path). Until this task runs, Task 12's live recreation of the Gemini note would execute against the old, unfixed capture logic — this is the step that actually delivers Tasks 1–10 to the running agent. `obsidian-clip-beautifier` (the other skill in this same package) is confirmed out of scope: it has no `manifest.json` of its own (only CSS/JSON assets and one script), and this plan changes none of its files.

**Files:**
- Sync (copy, not edit — these become identical to the repo copy, nothing here is hand-written): from `E:\skill\skills\web-to-obsidian\` to `C:\Users\LTC\plugins\driftnote\skills\web-to-obsidian\`:
  - `scripts\save_capture.py`
  - `SKILL.md`
  - `references\tavily.md`
  - `references\browser-capture.md`
- Run: `C:\Users\LTC\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py`
- Run: `C:\Users\LTC\.codex\skills\.system\plugin-creator\scripts\read_marketplace_name.py`
- Run: `C:\Users\LTC\.codex\skills\.system\plugin-creator\scripts\update_plugin_cachebuster.py`

- [ ] **Step 1: Run the full test suite against the repo source**

Run: `python -m unittest discover -s tests -q` (from `E:\skill`)
Expected: all tests PASS, including every test added in Tasks 1–9.

- [ ] **Step 2: Validate the plugin source**

Run: `python3 "C:/Users/LTC/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py" "E:/skill"`
Expected: validation reports no errors.

- [ ] **Step 3: Copy the four changed files into the installed plugin copy**

```bash
cp "E:/skill/skills/web-to-obsidian/scripts/save_capture.py" \
   "C:/Users/LTC/plugins/driftnote/skills/web-to-obsidian/scripts/save_capture.py"
cp "E:/skill/skills/web-to-obsidian/SKILL.md" \
   "C:/Users/LTC/plugins/driftnote/skills/web-to-obsidian/SKILL.md"
cp "E:/skill/skills/web-to-obsidian/references/tavily.md" \
   "C:/Users/LTC/plugins/driftnote/skills/web-to-obsidian/references/tavily.md"
cp "E:/skill/skills/web-to-obsidian/references/browser-capture.md" \
   "C:/Users/LTC/plugins/driftnote/skills/web-to-obsidian/references/browser-capture.md"
```

Verify: `diff "E:/skill/skills/web-to-obsidian/scripts/save_capture.py" "C:/Users/LTC/plugins/driftnote/skills/web-to-obsidian/scripts/save_capture.py"` prints nothing.

- [ ] **Step 4: Read the personal marketplace name**

Run: `python3 "C:/Users/LTC/.codex/skills/.system/plugin-creator/scripts/read_marketplace_name.py"`
Expected: prints `personal`.

- [ ] **Step 5: Bump the installed plugin's cachebuster**

Run: `python3 "C:/Users/LTC/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py" "C:/Users/LTC/plugins/driftnote"`
Expected: `C:\Users\LTC\plugins\driftnote\plugin.json`'s `"version"` changes from `0.5.0+codex.20260922023520` to `0.5.0+codex.<new-UTC-timestamp>` — prefix `0.5.0` preserved, only the `+codex.` suffix replaced (Cachebuster Policy, `installing-and-updating.md:93-111`).

- [ ] **Step 6: Reinstall**

Run: `codex plugin add driftnote@personal`
Expected: command succeeds; no marketplace-file edits needed since `personal` is the default marketplace.

- [ ] **Step 7: Confirm the reload**

In a new task/thread (plugin updates only take effect in a fresh thread per `installing-and-updating.md:141-144`), ask Codex which Driftnote version is active and confirm it matches the new cachebuster from Step 5.

- [ ] **Step 8: No commit for the copy step** — the installed copy at `C:\Users\LTC\plugins\driftnote` is outside this repo's git history. Do not bump `E:\skill`'s own `.codex-plugin/plugin.json`, `plugin.json`, or `.claude-plugin/plugin.json` just to trigger this local reinstall; a real version bump for those is a separate, explicit release decision.

---

### Task 12: Recreate the Gemini File Search note (manual, after Task 11 reinstalls the plugin)

This is the one note-specific step from the earlier review — it must come last, after Task 11 has put the fixed pipeline where the live agent actually runs it, so the note is only touched once, by the fixed code. This step needs a live browser/extension session and cannot be scripted or unit-tested here; it is a runbook, not code.

A separate Codex session previously exercised this same fetch path against a different page (`https://ai.google.dev/gemini-api/docs/url-context?hl=vi`, not this note's `file-search` page) and reported success — that is evidence the mechanism can work, not evidence that this specific note's source has already been re-fetched. Treat Step 1 below as not yet done.

**Files:**
- Modify (at execution time only, not part of this code change): `E:\skill-obsidian\00 Inbox\Web\2026-09-22 - Tìm kiếm tệp - Interactions API - Google AI for Developers.md`

- [ ] **Step 1: Get a real capture of the live page**

Open `https://ai.google.dev/gemini-api/docs/file-search?hl=vi` in the ChatGPT browser extension (or another authorized browser context) and export the page's DOM/HTML per [browser-capture.md](skills/web-to-obsidian/references/browser-capture.md). Save it as UTF-8 to a temp file, e.g. `$env:TEMP\file-search.html`.

If the extension still cannot export DOM/HTML for this page, run the new fallback instead, using the *installed* plugin path (this is what the live agent actually resolves and runs, per `SKILL.md`'s own "For an installed skill..." instruction):

```powershell
python C:\Users\LTC\plugins\driftnote\skills\web-to-obsidian\scripts\save_capture.py `
  --url "https://ai.google.dev/gemini-api/docs/file-search?hl=vi" `
  --title "Tìm kiếm tệp - Interactions API | Google AI for Developers" `
  --capture-method manual --fetch-public-html --tavily auto `
  --refresh-existing --dry-run
```

- [ ] **Step 2: Dry-run against the existing note and read the result**

```powershell
python C:\Users\LTC\plugins\driftnote\skills\web-to-obsidian\scripts\save_capture.py `
  --url "https://ai.google.dev/gemini-api/docs/file-search?hl=vi" `
  --title "Tìm kiếm tệp - Interactions API | Google AI for Developers" `
  --content-file "$env:TEMP\file-search.html" --capture-method chrome `
  --refresh-existing --dry-run
```

If the result's `status` is `needs-review`, read every entry in `review_issues`, open the generated `Needs Review` draft note in the vault (do not treat the existing main note as touched), fix the capture, and re-run this step. Do not proceed to Step 3 until `status` is `dry-run` with no review issues.

- [ ] **Step 3: Back up the existing note before touching it**

```powershell
New-Item -ItemType Directory -Force -Path "E:\skill-obsidian\.driftnote-backups" | Out-Null
Copy-Item `
  "E:\skill-obsidian\00 Inbox\Web\2026-09-22 - Tìm kiếm tệp - Interactions API - Google AI for Developers.md" `
  "E:\skill-obsidian\.driftnote-backups\2026-09-22 - Tìm kiếm tệp - Interactions API - Google AI for Developers.md.bak"
```

- [ ] **Step 4: Compare the dry-run content against the live page**

Read the would-be note content and check, against the live page at the URL above: the "Giá" and "Bước tiếp theo" sections now have real body text, the table of contents has no duplicate destinations, no shell comment from a code sample appears as a heading, and any `#fragment` links from the original page (e.g. the `#pricing` reference near the top of the article) now point at a real Obsidian heading rather than a bare `#pricing` fragment.

- [ ] **Step 5: Refresh the real note**

Drop `--dry-run` and run the same command from Step 2 for real. Confirm the result `status` is `"refreshed"`, then open the note and confirm the `## Ghi chú của tôi` section, custom frontmatter, and original `captured` timestamp are all untouched.

- [ ] **Step 6: No commit** — this step only touches vault content outside the `skill` repository; there is nothing to commit here.

---

## Self-Review

**Spec coverage:**
- "HTML/DOM làm nguồn chính... fetch HTML công khai... Tavily chỉ là dự phòng" → Task 7 (`fetch_public_html`, wired ahead of the existing Tavily branch) + Task 10 (docs ordering).
- "Chuyển cấu trúc bằng code... fence cần ít nhất ba backtick... một backtick bọc nhiều dòng phải bị phát hiện" → Task 1 (`_find_unfenced_multiline_code_spans`); the HTML converter already emits valid fences (existing code, confirmed by reading `_HtmlMarkdownRenderer`, no change needed there).
- "Chỉ tạo mục lục sau khi kiểm tra... loại đích trùng" → Task 2 (`_find_duplicate_toc_destinations`) feeding Task 5's gate; TOC generation itself (`_generate_toc_from_headings`) is unchanged, the gate runs after it.
- "Cổng kiểm tra trước khi ghi... needs-review... không ghi đè" → Task 5. Confirmed with the user: a capture that passes every detector is trusted and written normally; `needs-review` fires only when a detector actually flags something — not a blanket "every Tavily capture needs review" policy. Revised further after the second round: the main note is never touched, but a labeled `type: capture-review` draft *is* written under `Needs Review/` (Task 5 Steps 8–9), so a human has something to open and fix rather than only a JSON error.
- Đúng cả 3 lần chuyển hướng, giới hạn 10 MiB, không gửi cookie/khóa, kiểm tra IP ở mỗi lần kết nối, cache/DNS-rebinding qua redirect → Task 7 (`_SafePublicHtmlRedirectHandler`, `_PUBLIC_HTML_MAX_BYTES`, content-type check, cookie/Authorization stripping on every hop).
- "Bổ sung trường hợp test cho các snippet và các trường hợp tương tự" → confirmed with the user as "keep the inline-snippet convention, just add more test cases in that style" (not a separate fixture file); satisfied by every task's per-function unit tests plus Task 6's two end-to-end regression snippets (broken shape / fixed shape). No `tests/fixtures/` directory added.
- "Đồng bộ nguồn plugin, tăng cache version, cài lại" → Task 11, using the real installed paths confirmed by reading `C:\Users\LTC\.agents\plugins\marketplace.json` (marketplace `personal`), `C:\Users\LTC\plugins\driftnote\plugin.json` (installed version `0.5.0+codex.20260922023520`), and `C:\Users\LTC\.codex\skills\.system\plugin-creator\references\installing-and-updating.md` (the cachebuster/reinstall flow) — not Obsidian CSS caching, and not `obsidian-clip-beautifier` (confirmed to have no `manifest.json` of its own, out of scope).
- "Tạo bản nháp, đối chiếu trang gốc, thay vùng nội dung nguồn, giữ Ghi chú của tôi" → Task 12 (renumbered after Task 11's plugin sync, since the live agent must run the fixed code, not the stale installed copy), using the existing `--refresh-existing`/`--dry-run` flags (unchanged code, already does exactly this per `_merge_refreshed_source_content`), plus a new non-overwriting backup to `.driftnote-backups` in Step 3 before the real refresh.
- The three items explicitly deferred after the prior comparison round are now designed and written in: `#fragment`→Obsidian-heading resolution with absolute-URL fallback → Task 9 (`_collect_fragment_heading_paths`, with its "nearest preceding heading for a sibling anchor" limitation pinned by its own test rather than left as an unverified claim); the HTML-vs-Markdown structural round-trip check → Task 8 (`_find_structural_content_loss`, wired into `_collect_content_review_issues` and both HTML-sourced paths); the `needs-review` draft note → folded into Task 5 as described above (this required relocating Task 5's gate later in `run_capture()`, after `title`/`captured_date`/`filename_title` are computed, and Task 7's `elif fetched_public_html:` insertion point was updated to match).
- The unaddressed process gap noted in the earlier review — the connected-extract `basic`→`advanced` retry policy in `tavily.md` not being followed for this note — is not a code task (it is agent-level judgment when the *connected* Tavily tool is used, not the script's own `--tavily` branch); it is called out in Task 10 Step 4's new "Ordering" section instead of a script change.

**Placeholder scan:** every step has real, complete code or a real, complete command — no "TBD", no "add appropriate validation", no unstated helper functions.

**Type consistency:** `_find_unfenced_multiline_code_spans` returns `list[tuple[int, int]]` everywhere it's used (Task 1 tests, Task 5's `_collect_content_review_issues`). `_extract_toc_block`/`_find_duplicate_toc_destinations` both take/return `str`/`list[str]` consistently between Tasks 2 and 5. `_find_empty_sections` returns `list[str]` of heading text (not full paths) consistently between Tasks 3, 5, and 6. `fetch_public_html(url: str, timeout: float = 15.0) -> str` signature matches every call site in Task 7 (the shared CLI `--timeout` default stays 30.0 — Task 10 Step 1 documents passing `--timeout 15` explicitly alongside `--fetch-public-html`, rather than changing the shared flag's default and risking existing Tavily-path tests that assert on it). The new `"public-html"` capture-method string is used identically in the `CAPTURE_METHODS` tuple, the `run_capture()` wiring, and the Task 7 integration test's assertion. `fetch_public_html`'s HTTP boundary (`urllib.request.build_opener(...).open(...)`) is intentionally distinct from `extract_with_tavily`'s (`urllib.request.urlopen(...)`), so Task 7 Step 7's fallback test mocks both independently rather than sharing one mock. `_collect_content_review_issues`'s new `source_html` keyword (Task 8) defaults to `None` everywhere except Task 5 Step 9's call site, which now passes `html_content if rich_html else None` — matching the variable Task 7 also populates (`html_content = fetched_html`) so the check applies uniformly across every rich-HTML path. `_render_review_note`/`_write_review_note` (Task 5) and `_collect_fragment_heading_paths` (Task 9) are each used with the exact same parameter names and types at every call site shown in their own task.
