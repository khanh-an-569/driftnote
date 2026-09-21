# Auto-TOC Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a captured note's content has no native TOC and at least 3 headings, synthesize a `[!toc]-` callout from those headings, in the same format as the existing native-TOC-clone feature.

**Architecture:** One new pure function `_generate_toc_from_headings(content: str) -> str` in `skills/web-to-obsidian/scripts/save_capture.py`, reusing existing `_escape_wikilink` and `_insert_toc_after_header` helpers; called once in `run_capture()` after `content` is finalized from any of its three sources (`--html-file`, `--content-file`, Tavily).

**Tech Stack:** Python standard library only (matches `save_capture.py`'s existing stdlib-only constraint), `unittest` for tests.

**Spec:** `docs/superpowers/specs/2026-09-21-auto-toc-fallback-design.md`

## Global Constraints

- Stdlib-only — no new `requirements-dev.txt` entries.
- Fallback only: skip entirely if `content` already contains `"[!toc]"`.
- Minimum 3 headings required, else return `""` (no TOC).
- Headings inside fenced code blocks (` ``` `) must never be treated as TOC entries.
- Must reuse the existing wikilink format exactly: single-segment path → `[[#Heading]]`; nested path → `[[#Parent#Child|Child]]` (via `_escape_wikilink`).
- Must not alter the native TOC-clone code path (`_render_toc_callout`, `_render_toc_list`) or any identity/canonicalization/duplicate logic.

---

### Task 1: `_generate_toc_from_headings` and its call site

**Files:**
- Modify: `skills/web-to-obsidian/scripts/save_capture.py`
- Test: `tests/test_save_capture.py`

**Interfaces:**
- Consumes: `_escape_wikilink(value: str) -> str` and `_insert_toc_after_header(markdown: str, toc: str) -> str` (both already exist, unchanged).
- Produces: `def _generate_toc_from_headings(content: str) -> str`, and a new line in `run_capture()` applying it to the finalized `content` variable.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_save_capture.py` (find the `SaveCaptureTests` class and add these as new methods; the module already exposes `save_capture` via the existing `importlib.util` loader at the top of the file, and `make_args(vault, **overrides)` is already defined there):

```python
    def test_content_file_capture_gets_generated_toc_for_three_or_more_headings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            content_file = Path(temp_dir) / "capture.md"
            content_file.write_text(
                "# Intro\n\nSome intro text.\n\n"
                "## First section\n\nBody one.\n\n"
                "## Second section\n\nBody two.\n\n"
                "### Second section detail\n\nNested body.\n",
                encoding="utf-8",
            )
            args = make_args(temp_dir, content_file=str(content_file))
            result = save_capture.run_capture(args)
            note = Path(str(result["path"])).read_text(encoding="utf-8")
            self.assertIn("> [!toc]- Table of contents", note)
            self.assertIn("> - [[#Intro]]", note)
            self.assertIn("> - [[#First section]]", note)
            self.assertIn("> - [[#Second section]]", note)
            self.assertIn("> - [[#Second section#Second section detail|Second section detail]]", note)

    def test_content_file_capture_with_fewer_than_three_headings_gets_no_toc(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            content_file = Path(temp_dir) / "capture.md"
            content_file.write_text(
                "# Intro\n\nSome intro text.\n\n## Only other heading\n\nBody.\n",
                encoding="utf-8",
            )
            args = make_args(temp_dir, content_file=str(content_file))
            result = save_capture.run_capture(args)
            note = Path(str(result["path"])).read_text(encoding="utf-8")
            self.assertNotIn("[!toc]", note)

    def test_generate_toc_from_headings_skips_when_toc_already_present(self) -> None:
        content = (
            "> [!toc]- Table of contents\n> - [[#A]]\n\n"
            "# A\n\n## B\n\n## C\n\n## D\n"
        )
        self.assertEqual(save_capture._generate_toc_from_headings(content), "")

    def test_generate_toc_from_headings_ignores_headings_in_code_fences(self) -> None:
        content = (
            "# Real heading one\n\n"
            "```python\n# Not a heading\n## Also not a heading\n```\n\n"
            "## Real heading two\n\n"
            "## Real heading three\n"
        )
        toc = save_capture._generate_toc_from_headings(content)
        self.assertNotIn("Not a heading", toc)
        self.assertIn("[[#Real heading one]]", toc)
        self.assertIn("[[#Real heading one#Real heading two|Real heading two]]", toc)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests.test_content_file_capture_gets_generated_toc_for_three_or_more_headings tests.test_save_capture.SaveCaptureTests.test_content_file_capture_with_fewer_than_three_headings_gets_no_toc tests.test_save_capture.SaveCaptureTests.test_generate_toc_from_headings_skips_when_toc_already_present tests.test_save_capture.SaveCaptureTests.test_generate_toc_from_headings_ignores_headings_in_code_fences -v`
Expected: the two `_generate_toc_from_headings`-calling tests fail with `AttributeError: module 'save_capture' has no attribute '_generate_toc_from_headings'`; the two `run_capture`-based tests fail because no `[!toc]` line appears / assertion errors, since the function doesn't exist yet and nothing calls it.

- [ ] **Step 3: Implement `_generate_toc_from_headings`**

Add this function to `skills/web-to-obsidian/scripts/save_capture.py` near the existing TOC functions (immediately after `_insert_toc_after_header`, before `def html_to_markdown`):

```python
_MARKDOWN_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_CODE_FENCE_PATTERN = re.compile(r"^```")


def _extract_markdown_headings(content: str) -> list[tuple[int, str]]:
    headings: list[tuple[int, str]] = []
    in_code_fence = False
    for line in content.splitlines():
        if _CODE_FENCE_PATTERN.match(line):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        match = _MARKDOWN_HEADING_PATTERN.match(line)
        if match:
            headings.append((len(match.group(1)), match.group(2).strip()))
    return headings


def _generate_toc_from_headings(content: str) -> str:
    if "[!toc]" in content:
        return ""
    headings = _extract_markdown_headings(content)
    if len(headings) < 3:
        return ""

    lines: list[str] = []
    stack: list[tuple[int, str]] = []
    for level, text in headings:
        while stack and stack[-1][0] >= level:
            stack.pop()
        ancestors = tuple(entry[1] for entry in stack)
        path = ancestors + (text,)
        stack.append((level, text))
        destination = "#" + "#".join(_escape_wikilink(part) for part in path)
        escaped_text = _escape_wikilink(text)
        if len(path) == 1:
            wikilink = f"[[{destination}]]"
        else:
            wikilink = f"[[{destination}|{escaped_text}]]"
        depth = len(path) - 1
        lines.append(f"{'  ' * depth}- {wikilink}")

    toc_lines = ["> [!toc]- Table of contents"]
    toc_lines.extend(f"> {line}" for line in lines)
    return "\n".join(toc_lines)
```

Then, in `run_capture()`, find the point where `content` is fully finalized — this is immediately after the Tavily block ends and before `capture_method = args.capture_method` is computed (i.e., right after the `if not tavily_depth and last_error:` block's `warnings.append(...)` line, at the same indentation as the surrounding `if args.tavily != "off" and needs_content:` block, so it runs regardless of which branch set `content`). Add:

```python
    content = _insert_toc_after_header(content, _generate_toc_from_headings(content))
```

Place this as the next top-level statement after the entire Tavily `if`/`else` block, before `capture_method = args.capture_method`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_save_capture.SaveCaptureTests.test_content_file_capture_gets_generated_toc_for_three_or_more_headings tests.test_save_capture.SaveCaptureTests.test_content_file_capture_with_fewer_than_three_headings_gets_no_toc tests.test_save_capture.SaveCaptureTests.test_generate_toc_from_headings_skips_when_toc_already_present tests.test_save_capture.SaveCaptureTests.test_generate_toc_from_headings_ignores_headings_in_code_fences -v`
Expected: `OK` (4 tests pass).

- [ ] **Step 5: Run the full suite and repo-wide checks**

Run, in order:
```bash
python -m unittest discover -s tests -q
python scripts/check_no_secrets.py --root .
python -m compileall -q skills scripts tests
git diff --check
```
Expected: full suite green (no regressions in any existing `test_save_capture.py`, `test_audit_sensitive_urls.py`, or other test — in particular, existing tests that assert exact note content for pages with ≥3 headings and no native TOC may now need their expected content updated to account for the new TOC callout; if any existing test breaks this way, that is expected — update its expected string to include the generated TOC rather than treating it as a regression). All other checks clean.

- [ ] **Step 6: Commit**

```bash
git add skills/web-to-obsidian/scripts/save_capture.py tests/test_save_capture.py
git commit -m "feat: auto-generate a TOC callout from headings when no native TOC exists"
```

- [ ] **Step 7: Push to the existing PR branch**

```bash
git push
```

This lands the change directly on `pr/obsidian-excalidraw-mindmap`, updating the already-open PR in place, per explicit instruction — do not open a new branch or PR for this change.
