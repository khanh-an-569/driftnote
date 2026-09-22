from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import io
import json
import multiprocessing
import re
import sys
import tempfile
import threading
import unittest
import urllib.error
from unittest import mock
from pathlib import Path
from typing import Any

import yaml


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "web-to-obsidian"
    / "scripts"
    / "save_capture.py"
)
SPEC = importlib.util.spec_from_file_location("save_capture", SCRIPT_PATH)
assert SPEC and SPEC.loader
save_capture = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = save_capture
SPEC.loader.exec_module(save_capture)


class FakeHttpResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeHttpResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def make_args(vault: str, **overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "vault": vault,
        "url": "https://Example.COM/story/?utm_source=test&b=2&a=1#section",
        "title": "Một bài viết: hữu ích?",
        "author": "Tác giả",
        "published": "2026-09-13",
        "platform": "",
        "content_type": "article",
        "capture_method": "chrome",
        "content_file": None,
        "html_file": None,
        "selection_file": None,
        "summary": "",
        "why": "Dùng cho dự án second brain",
        "tag": [],
        "topic": ["knowledge-management"],
        "cssclass": [],
        "folder": "00 Inbox/Web",
        "captured": "2026-09-13T10:00:00+07:00",
        "tavily": "off",
        "min_content_chars": 400,
        "timeout": 30.0,
        "confirm_social_permalink": False,
        "allow_text_only": False,
        "refresh_existing": False,
        "dry_run": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def capture_in_process(
    vault: str,
    title: str,
    start_event: Any,
    result_queue: Any,
) -> None:
    start_event.wait(timeout=5.0)
    try:
        result = save_capture.run_capture(
            make_args(vault, url="https://example.com/process-race", title=title)
        )
    except Exception as exc:  # pragma: no cover - returned for parent assertion
        result_queue.put({"error_type": type(exc).__name__, "error": str(exc)})
    else:
        result_queue.put({"status": result["status"], "path": result["path"]})


class SaveCaptureTests(unittest.TestCase):
    def test_content_file_with_html_is_detected_and_preserves_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            content_file = Path(temp_dir) / "browser-capture.txt"
            content_file.write_text(
                '<main><h2>Report</h2><p>Read <a href="/study">the study</a>.</p></main>',
                encoding="utf-8",
            )
            result = save_capture.run_capture(
                make_args(
                    temp_dir,
                    url="https://example.com/article",
                    title="Report",
                    content_file=str(content_file),
                )
            )

            note = Path(str(result["path"])).read_text(encoding="utf-8")
            self.assertIn("[the study](https://example.com/study)", note)
            self.assertIn("### Report", note)

    def test_full_article_capture_preserves_every_content_link_without_loss(self) -> None:
        """Reconstruct the note from a raw capture and diff its links against the source.

        This is the type-detection contract end to end: the helper alone (no agent
        flag) must decide the capture is HTML, convert it, and the resulting link set
        must match the source article's content links exactly - nothing dropped, and
        chrome/script-only or literal code-text hrefs must not leak in as real links.
        """
        html = """
        <nav><a href="/nav-only">Skip navigation</a></nav>
        <script>var link = "<a href='/script-only'>fake</a>";</script>
        <main>
          <h1>Deep sea discovery</h1>
          <p>Researchers published <a href="/sources/paper">the paper</a> this week.</p>
          <ul>
            <li>See the <a href="https://example.com/data/raw">raw dataset</a>.</li>
            <li>Compare with <a href="/sources/prior-study">a prior study</a>.</li>
          </ul>
          <table>
            <tr><th>Site</th><th>Report</th></tr>
            <tr><td>Station A</td><td><a href="/reports/station-a">Station A report</a></td></tr>
          </table>
          <blockquote>
            <p>As noted in <a href="/sources/interview">an interview</a>, the team was surprised.</p>
          </blockquote>
          <pre><code>&lt;a href="/should-not-be-linked"&gt;fake code link&lt;/a&gt;</code></pre>
        </main>
        """

        with tempfile.TemporaryDirectory() as temp_dir:
            content_file = Path(temp_dir) / "browser-capture.txt"
            content_file.write_text(html, encoding="utf-8")

            result = save_capture.run_capture(
                make_args(
                    temp_dir,
                    url="https://example.com/article",
                    title="Deep sea discovery",
                    content_file=str(content_file),
                )
            )

            note = Path(str(result["path"])).read_text(encoding="utf-8")

        # Reconstruct just the captured article body (excluding the note's own
        # "source" backlink and frontmatter) to diff against the original page.
        source_content = note.split("web-to-obsidian:source-content:start -->", 1)[1]
        source_content = source_content.split("<!-- web-to-obsidian:source-content:end", 1)[0]

        # The article's real content links - everything a reader could click through to.
        expected_links = {
            "https://example.com/sources/paper",
            "https://example.com/data/raw",
            "https://example.com/sources/prior-study",
            "https://example.com/reports/station-a",
            "https://example.com/sources/interview",
        }
        found_links = set(re.findall(r"\]\((https://example\.com/[^)\s]+)\)", source_content))
        self.assertEqual(expected_links, found_links)

        # Chrome-chrome (nav) and script-only hrefs never counted as content links.
        self.assertNotIn("/nav-only", note)
        self.assertNotIn("/script-only", note)
        # A link-shaped string that is only literal code text must stay text, not a link.
        self.assertIn("/should-not-be-linked", note)
        self.assertNotIn("[fake code link](", note)
        self.assertNotIn("](https://example.com/should-not-be-linked)", note)

    def test_markdown_code_example_is_not_treated_as_html_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            content_file = Path(temp_dir) / "capture.md"
            content_file.write_text(
                "# HTML example\n\n```html\n<main><a href=\"/study\">study</a></main>\n```\n",
                encoding="utf-8",
            )
            result = save_capture.run_capture(
                make_args(
                    temp_dir,
                    content_file=str(content_file),
                    allow_text_only=True,
                )
            )

            note = Path(str(result["path"])).read_text(encoding="utf-8")
            self.assertIn('```html\n<main><a href="/study">study</a></main>\n```', note)
            self.assertNotIn("[study](https://example.com/study)", note)

    def test_markdown_with_inline_html_keeps_markdown_heading(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            content_file = Path(temp_dir) / "capture.md"
            content_file.write_text(
                '# Notes\n\nRead <a href="/study">study</a>.\n',
                encoding="utf-8",
            )
            result = save_capture.run_capture(
                make_args(temp_dir, content_file=str(content_file), allow_text_only=True)
            )

            note = Path(str(result["path"])).read_text(encoding="utf-8")
            self.assertIn('# Notes\n\nRead <a href="/study">study</a>.', note)

    def test_html_file_rejects_plain_text_instead_of_marking_it_rich(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            html_file = Path(temp_dir) / "page.html"
            html_file.write_text("This browser output has no HTML structure.", encoding="utf-8")
            with self.assertRaisesRegex(save_capture.CaptureError, "does not contain HTML"):
                save_capture.run_capture(
                    make_args(temp_dir, html_file=str(html_file), dry_run=True)
                )

    def test_browser_plain_text_capture_requires_explicit_text_only_choice(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            content_file = Path(temp_dir) / "article.txt"
            content_file.write_text("Linked article without href data.", encoding="utf-8")
            with self.assertRaisesRegex(save_capture.CaptureError, "--html-file"):
                save_capture.run_capture(
                    make_args(temp_dir, content_file=str(content_file), dry_run=True)
                )

    def test_browser_plain_text_capture_warns_about_lost_hyperlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            content_file = Path(temp_dir) / "article.txt"
            content_file.write_text(
                "The report cites another study but the browser text has no href.",
                encoding="utf-8",
            )
            result = save_capture.run_capture(
                make_args(
                    temp_dir,
                    content_file=str(content_file),
                    dry_run=True,
                    allow_text_only=True,
                )
            )

        self.assertTrue(
            any("hyperlinks" in warning for warning in result["warnings"]),
            result["warnings"],
        )

    def test_html_to_markdown_preserves_links_emphasis_and_images(self) -> None:
        html = """
        <html><body><nav>Skip navigation</nav><main>
          <h1>Rich lesson</h1>
          <p><strong>Bold</strong> and <em>italic</em>
             <a href="/docs/next">next lesson</a>.</p>
          <figure>
            <img src="../images/plot.png" alt="Training plot">
            <figcaption>Figure one</figcaption>
          </figure>
          <script>window.evil = true</script>
        </main></body></html>
        """

        markdown = save_capture.html_to_markdown(
            html,
            "https://example.com/course/chapter/",
        )

        self.assertIn("# Rich lesson", markdown)
        self.assertIn("**Bold**", markdown)
        self.assertIn("*italic*", markdown)
        self.assertIn("[next lesson](https://example.com/docs/next)", markdown)
        self.assertIn(
            "![Training plot](https://example.com/course/images/plot.png)",
            markdown,
        )
        self.assertIn("*Figure one*", markdown)
        self.assertNotIn("Skip navigation", markdown)
        self.assertNotIn("window.evil", markdown)

    def test_html_to_markdown_preserves_tables_math_and_maps_details_to_callouts(self) -> None:
        html = r"""
        <main>
          <table>
            <thead><tr><th>Model</th><th>Accuracy</th></tr></thead>
            <tbody><tr><td>Baseline</td><td>91%</td></tr></tbody>
          </table>
          <p>Inline <span class="math inline">\(x^2 + y^2\)</span>.</p>
          <div class="math display">\[E = mc^2\]</div>
          <details class="callout-checkpoint" open><summary>Checkpoint 1.1</summary>
            <p><strong>Question:</strong> What changes?</p>
          </details>
          <details class="callout-quiz-question"><summary>Self-Check: Question</summary>
            <p>Choose one answer.</p>
          </details>
        </main>
        """

        markdown = save_capture.html_to_markdown(html, "https://example.com/lesson")

        self.assertIn("| Model | Accuracy |", markdown)
        self.assertIn("| --- | --- |", markdown)
        self.assertIn("| Baseline | 91% |", markdown)
        self.assertIn("$x^2 + y^2$", markdown)
        self.assertIn("$$\nE = mc^2\n$$", markdown)
        self.assertIn("> [!success]+ Checkpoint 1.1", markdown)
        self.assertIn("> **Question:** What changes?", markdown)
        self.assertIn("> [!question]- Self-Check: Question", markdown)
        self.assertIn("> Choose one answer.", markdown)
        self.assertNotIn("<details", markdown)

    def test_display_math_nested_in_callout_paragraph_starts_on_its_own_block(self) -> None:
        html = r"""
        <main>
          <details class="callout-perspective" open>
            <summary><strong>Systems Perspective 1.2</strong></summary>
            <div>
              <p>Execution time is bounded below:
                <span class="math display">\[T \geq \max(C, M, I)\]</span>
              </p>
            </div>
          </details>
        </main>
        """

        markdown = save_capture.html_to_markdown(html, "https://example.com/lesson")

        self.assertIn(
            "> Execution time is bounded below:\n>\n"
            "> $$\n"
            "> T \\geq \\max(C, M, I)\n"
            "> $$",
            markdown,
        )
        self.assertNotIn("below: $$", markdown)

    def test_display_math_after_direct_container_text_starts_on_its_own_block(self) -> None:
        html = r"""
        <main>
          <details class="callout-perspective" open>
            <summary>Systems Perspective 1.1</summary>
            <div>Diagnostic equation:
              <span class="math display">\[T = C + M\]</span>
              Follow-up text.
            </div>
          </details>
        </main>
        """

        markdown = save_capture.html_to_markdown(html, "https://example.com/lesson")

        self.assertIn(
            "> Diagnostic equation:\n>\n"
            "> $$\n"
            "> T = C + M\n"
            "> $$\n>\n"
            "> Follow-up text.",
            markdown,
        )
        self.assertNotIn("equation: $$", markdown)

    def test_quarto_title_block_becomes_a_styled_obsidian_header(self) -> None:
        html = """
        <main>
          <header id="title-block-header" class="quarto-title-block default">
            <nav class="quarto-page-breadcrumbs">
              <a href="../part.html">Part I</a><a href="chapter.html">Chapter</a>
            </nav>
            <div class="quarto-title"><h1 class="title">Deployment framework</h1></div>
          </header>
          <section><h1>ML Systems</h1><h2>Purpose</h2></section>
        </main>
        """

        markdown = save_capture.html_to_markdown(html, "https://example.com/book/page.html")

        self.assertIn("> [!web-header] Deployment framework", markdown)
        self.assertIn(
            "> [Part I](https://example.com/part.html) · "
            "[Chapter](https://example.com/book/chapter.html)",
            markdown,
        )
        self.assertNotIn("# Deployment framework", markdown)

    def test_quarto_toc_becomes_a_collapsed_callout_with_local_heading_links(self) -> None:
        html = """
        <html><body>
          <nav id="TOC" role="doc-toc">
            <h2>On this page</h2>
            <ul>
              <li><a href="#chapter">Chapter</a>
                <ul>
                  <li><a href="#section-a">Section A</a>
                    <ul><li><a href="#detail">Detail</a></li></ul>
                  </li>
                  <li><a href="#missing">Missing section</a></li>
                  <li><a href="https://example.com/other">External section</a></li>
                </ul>
              </li>
            </ul>
          </nav>
          <main>
            <header id="title-block-header">
              <h1 class="title">Deployment framework</h1>
            </header>
            <section id="chapter"><h1>Chapter</h1>
              <section id="section-a"><h2>Section A</h2>
                <h3 id="detail">Detail</h3>
              </section>
            </section>
          </main>
        </body></html>
        """

        markdown = save_capture.html_to_markdown(html, "https://example.com/book/page.html")

        expected_toc = (
            "> [!toc]- On this page\n"
            "> - [[#Chapter]]\n"
            ">   - [[#Chapter#Section A|Section A]]\n"
            ">     - [[#Chapter#Section A#Detail|Detail]]"
        )
        self.assertIn(expected_toc, markdown)
        self.assertLess(markdown.index("[!web-header]"), markdown.index("[!toc]"))
        self.assertLess(markdown.index("[!toc]"), markdown.index("# Chapter"))
        self.assertNotIn("Missing section", markdown)
        self.assertNotIn("External section", markdown)

    def test_quarto_lightbox_uses_the_rendered_image_as_click_target(self) -> None:
        html = """
        <main><p>
          <a class="lightbox" href="diagram.svg">
            <img src="page_files/mediabag/diagram.svg" alt="Architecture">
          </a>
        </p></main>
        """

        markdown = save_capture.html_to_markdown(
            html,
            "https://example.com/chapter/page.html",
        )

        image_url = "https://example.com/chapter/page_files/mediabag/diagram.svg"
        self.assertIn(f"[![Architecture]({image_url})]({image_url})", markdown)
        self.assertNotIn("https://example.com/chapter/diagram.svg", markdown)

    def test_plain_currency_is_escaped_without_changing_tex_math(self) -> None:
        html = r"""
        <main>
          <p>Hardware costs $999 and logging costs ~$2,000.</p>
          <p>Energy is <span class="math inline">\(E = mc^2\)</span>.</p>
          <table><tr><th>Item</th><th>Cost</th></tr>
            <tr><td>Device</td><td>$10</td></tr></table>
        </main>
        """

        markdown = save_capture.html_to_markdown(html, "https://example.com/page")

        self.assertIn(r"Hardware costs \$999 and logging costs ~\$2,000.", markdown)
        self.assertIn(r"| Device | \$10 |", markdown)
        self.assertIn("$E = mc^2$", markdown)

    def test_complex_table_html_fallback_removes_active_content(self) -> None:
        html = """
        <main><table><tr>
          <th colspan="2"><a href="javascript:alert(1)">Heading</a></th>
        </tr><tr><td onmouseover="alert(2)">Safe cell</td><td>Other</td></tr>
        <tr><td colspan="2">
          <object data="javascript:alert(3)">Object text</object>
          <link rel="stylesheet" href="https://evil.example/x.css">
          <meta http-equiv="refresh" content="0;url=javascript:alert(4)">
          <base href="https://evil.example/">
        </td></tr>
        </table></main>
        """

        markdown = save_capture.html_to_markdown(html, "https://example.com/lesson")

        self.assertIn('<th colspan="2">', markdown)
        self.assertIn("Heading", markdown)
        self.assertNotIn("javascript:", markdown)
        self.assertNotIn("onmouseover", markdown)
        self.assertNotIn("<object", markdown)
        self.assertNotIn("<link", markdown)
        self.assertNotIn("<meta", markdown)
        self.assertNotIn("<base", markdown)

    def test_html_inside_main_skips_navigation_chrome(self) -> None:
        html = """
        <main>
          <nav><a href="/toc">Inside navigation</a></nav>
          <h1>Article title</h1><p>Article body.</p>
          <a id="quarto-back-to-top" role="button">Back to top</a>
        </main>
        """

        markdown = save_capture.html_to_markdown(html, "https://example.com/lesson")

        self.assertIn("# Article title", markdown)
        self.assertIn("Article body.", markdown)
        self.assertNotIn("Inside navigation", markdown)
        self.assertNotIn("Back to top", markdown)

    def test_refresh_legacy_note_fails_closed_on_ambiguous_personal_notes_boundary(self) -> None:
        legacy_note = """
---
type: source
capture_method: chrome
link_only: false
---

## Nội dung nguồn

## Ghi chú của tôi

This heading belongs to the captured article.

## Ghi chú của tôi

Actual personal note.
"""

        with self.assertRaisesRegex(save_capture.CaptureError, "boundary"):
            save_capture._merge_refreshed_source_content(
                legacy_note,
                "New source content",
                "chrome",
            )

    def test_html_file_capture_converts_dom_before_writing_note(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            html_file = Path(temp_dir) / "page.html"
            html_file.write_text(
                '<main><h2>Learning objectives</h2>'
                '<p>Read <a href="/guide">the guide</a>.</p></main>',
                encoding="utf-8",
            )

            result = save_capture.run_capture(
                make_args(
                    temp_dir,
                    url="https://example.com/course/lesson",
                    title="HTML lesson",
                    html_file=str(html_file),
                )
            )

            note = Path(str(result["path"])).read_text(encoding="utf-8")
            self.assertEqual(result["status"], "created")
            self.assertIn("### Learning objectives", note)
            self.assertNotIn("\n## Nội dung nguồn\n", note)
            self.assertNotRegex(note, r"(?m)^ +### Learning objectives$")
            self.assertIn("[the guide](https://example.com/guide)", note)

    def test_refresh_existing_replaces_only_source_content_and_keeps_my_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plain_file = Path(temp_dir) / "plain.txt"
            plain_file.write_text("Old flattened content", encoding="utf-8")
            first = save_capture.run_capture(
                make_args(
                    temp_dir,
                    url="https://example.com/refresh-me",
                    title="Refresh target",
                    content_file=str(plain_file),
                    allow_text_only=True,
                )
            )
            note_path = Path(str(first["path"]))
            note_path.write_text(
                note_path.read_text(encoding="utf-8")
                + "My durable annotation\n",
                encoding="utf-8",
            )

            html_file = Path(temp_dir) / "page.html"
            html_file.write_text(
                '<main><h2>New structured content</h2>'
                '<p><strong>Preserved structure</strong></p></main>',
                encoding="utf-8",
            )
            refreshed = save_capture.run_capture(
                make_args(
                    temp_dir,
                    url="https://example.com/refresh-me",
                    title="Refresh target",
                    html_file=str(html_file),
                    refresh_existing=True,
                )
            )

            note = note_path.read_text(encoding="utf-8")
            self.assertEqual(refreshed["status"], "refreshed")
            self.assertEqual(Path(str(refreshed["path"])), note_path)
            self.assertNotIn("Old flattened content", note)
            self.assertIn("## New structured content", note)
            self.assertIn("**Preserved structure**", note)
            self.assertIn("My durable annotation", note)
            self.assertEqual(len(list(Path(temp_dir).rglob("*.md"))), 1)

    def test_refresh_link_only_note_adds_source_and_removes_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first = save_capture.run_capture(
                make_args(temp_dir, url="https://example.com/link-only", title="Link only")
            )
            note_path = Path(str(first["path"]))
            note_path.write_text(
                note_path.read_text(encoding="utf-8") + "My durable annotation\n",
                encoding="utf-8",
            )
            content_file = Path(temp_dir) / "extracted.md"
            content_file.write_text(
                "# Extracted page\n\nRead [the guide](https://example.com/guide).",
                encoding="utf-8",
            )

            refreshed = save_capture.run_capture(
                make_args(
                    temp_dir,
                    url="https://example.com/link-only",
                    title="Link only",
                    capture_method="tavily-basic",
                    content_file=str(content_file),
                    refresh_existing=True,
                )
            )

            note = note_path.read_text(encoding="utf-8")
            self.assertEqual(refreshed["status"], "refreshed")
            self.assertFalse(refreshed["link_only"])
            self.assertIn("link_only: false", note)
            self.assertIn("capture_method: tavily-basic", note)
            self.assertIn("[the guide](https://example.com/guide)", note)
            self.assertIn("My durable annotation", note)
            self.assertNotIn("Link-only capture", note)
            self.assertEqual(len(list(Path(temp_dir).rglob("*.md"))), 2)

    def test_configures_utf8_console(self) -> None:
        class FakeStream:
            options: dict[str, str] | None = None

            def reconfigure(self, **kwargs: str) -> None:
                self.options = kwargs

        stdout = FakeStream()
        stderr = FakeStream()
        with mock.patch.object(save_capture.sys, "stdout", stdout), mock.patch.object(
            save_capture.sys, "stderr", stderr
        ):
            save_capture._configure_utf8_console()

        self.assertEqual(stdout.options, {"encoding": "utf-8", "errors": "replace"})
        self.assertEqual(stderr.options, {"encoding": "utf-8", "errors": "replace"})

    def test_dotenv_loads_values_without_overriding_process_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "TAVILY_API_KEY=from-file\n"
                "OBSIDIAN_VAULT_PATH=E:/skill-obsidian # local vault\n",
                encoding="utf-8",
            )
            with mock.patch.dict(
                save_capture.os.environ, {"TAVILY_API_KEY": "from-process"}, clear=True
            ):
                loaded = save_capture.load_dotenv(workspace=Path(temp_dir))
                self.assertEqual(loaded, env_path.resolve())
                self.assertEqual(save_capture.os.environ["TAVILY_API_KEY"], "from-process")
                self.assertEqual(
                    save_capture.os.environ["OBSIDIAN_VAULT_PATH"], "E:/skill-obsidian"
                )

    def test_dotenv_falls_back_to_central_repo_env_outside_the_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository = root / "skill-repository"
            background_workspace = root / "background-task"
            script_path = (
                repository
                / "skills"
                / "web-to-obsidian"
                / "scripts"
                / "save_capture.py"
            )
            background_workspace.mkdir(parents=True)
            repository.mkdir(parents=True)
            central_env = repository / ".env"
            central_env.write_text(
                "WEB_TO_OBSIDIAN_VAULT_PATH=E:/web-vault\n",
                encoding="utf-8",
            )

            with mock.patch.dict(save_capture.os.environ, {}, clear=True):
                loaded = save_capture.load_dotenv(
                    workspace=background_workspace,
                    script_path=script_path,
                )

                self.assertEqual(loaded, central_env.resolve())
                self.assertEqual(
                    save_capture.os.environ["WEB_TO_OBSIDIAN_VAULT_PATH"],
                    "E:/web-vault",
                )

    def test_dotenv_ignores_variables_outside_the_capture_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "TAVILY_API_KEY=allowed\n"
                "OBSIDIAN_VAULT_PATH=E:/allowed-vault\n"
                "HTTPS_PROXY=https://attacker.invalid\n"
                "SSL_CERT_FILE=attacker.pem\n",
                encoding="utf-8",
            )
            with mock.patch.dict(save_capture.os.environ, {}, clear=True):
                save_capture.load_dotenv(workspace=Path(temp_dir))
                self.assertEqual(save_capture.os.environ["TAVILY_API_KEY"], "allowed")
                self.assertEqual(
                    save_capture.os.environ["OBSIDIAN_VAULT_PATH"], "E:/allowed-vault"
                )
                self.assertNotIn("HTTPS_PROXY", save_capture.os.environ)
                self.assertNotIn("SSL_CERT_FILE", save_capture.os.environ)

    def test_resolves_vault_from_cli_env_then_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "driftnote.yaml").write_text(
                'vault_root: "E:/yaml-vault"\n', encoding="utf-8"
            )
            with mock.patch.dict(save_capture.os.environ, {}, clear=True):
                self.assertEqual(
                    save_capture.resolve_vault(None, workspace=workspace), "E:/yaml-vault"
                )
                save_capture.os.environ["OBSIDIAN_VAULT_PATH"] = "E:/env-vault"
                self.assertEqual(
                    save_capture.resolve_vault(None, workspace=workspace), "E:/env-vault"
                )
                self.assertEqual(
                    save_capture.resolve_vault("E:/cli-vault", workspace=workspace),
                    "E:/cli-vault",
                )

    def test_skill_specific_vault_precedes_legacy_default(self) -> None:
        with mock.patch.dict(
            save_capture.os.environ,
            {
                "WEB_TO_OBSIDIAN_VAULT_PATH": "E:/web-vault",
                "OBSIDIAN_VAULT_PATH": "E:/shared-default-vault",
            },
            clear=True,
        ):
            self.assertEqual(
                save_capture.resolve_vault(None),
                "E:/web-vault",
            )

    def test_canonicalize_removes_tracking_without_reordering_or_trimming_path(self) -> None:
        actual = save_capture.canonicalize_url(
            "HTTPS://Example.COM/story/?utm_source=test&b=2&a=1#section"
        )
        self.assertEqual(actual, "https://example.com/story/?b=2&a=1")

    def test_canonicalize_brackets_ipv6_hosts(self) -> None:
        actual = save_capture.canonicalize_url("https://[2001:db8::1]:8443/a/")
        self.assertEqual(actual, "https://[2001:db8::1]:8443/a/")

    def test_social_feed_url_requires_a_permalink_before_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(save_capture.CaptureError) as raised:
                save_capture.run_capture(
                    make_args(
                        temp_dir,
                        url="https://www.facebook.com/",
                        content_type="social",
                        capture_method="selection",
                    )
                )

        message = str(raised.exception)
        self.assertIn("permalink", message.lower())
        self.assertIn("Copy link", message)

    def test_social_post_permalinks_are_accepted_without_confirmation(self) -> None:
        urls = (
            "https://www.facebook.com/example/posts/1234567890",
            "https://www.facebook.com/story.php?story_fbid=1234567890&id=42",
            "https://www.instagram.com/p/ABC123xyz/",
            "https://www.instagram.com/reel/REEL123xyz/",
        )

        for url in urls:
            with self.subTest(url=url), tempfile.TemporaryDirectory() as temp_dir:
                result = save_capture.run_capture(
                    make_args(
                        temp_dir,
                        url=url,
                        content_type="social",
                        capture_method="selection",
                        dry_run=True,
                    )
                )

                self.assertEqual(result["status"], "dry-run")

    def test_confirmation_changes_an_unrecognized_social_url_to_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            unconfirmed = make_args(
                temp_dir,
                url="https://www.instagram.com/example-profile/",
                content_type="social",
                capture_method="selection",
                dry_run=True,
            )
            with self.assertRaises(save_capture.CaptureError):
                save_capture.run_capture(unconfirmed)

            result = save_capture.run_capture(
                make_args(
                    temp_dir,
                    url="https://www.instagram.com/example-profile/",
                    content_type="social",
                    capture_method="selection",
                    confirm_social_permalink=True,
                    dry_run=True,
                )
            )

        self.assertEqual(result["status"], "dry-run")

    def test_social_permalink_confirmation_is_available_from_the_cli(self) -> None:
        args, unknown = save_capture.build_parser().parse_known_args(
            [
                "--url",
                "https://www.instagram.com/example-profile/",
                "--content-type",
                "social",
                "--confirm-social-permalink",
            ]
        )

        self.assertEqual(unknown, [])
        self.assertTrue(args.confirm_social_permalink)

    def test_tavily_rejects_private_and_sensitive_urls(self) -> None:
        self.assertFalse(save_capture.is_safe_public_url_for_tavily("http://127.0.0.1/a")[0])
        self.assertFalse(
            save_capture.is_safe_public_url_for_tavily("https://example.com/a?token=secret")[0]
        )
        self.assertFalse(
            save_capture.is_safe_public_url_for_tavily(
                "https://example.com/a?X-Amz-Credential=fake&X-Amz-Signature=fake"
            )[0]
        )
        self.assertTrue(save_capture.is_safe_public_url_for_tavily("https://example.com/a")[0])

    def test_sensitive_url_values_are_redacted_before_storage_and_hashing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_secret = "test-only-secret-value"
            result = save_capture.run_capture(
                make_args(
                    temp_dir,
                    url=(
                        "https://user:pass@example.com/story/?utm_source=test&ok=1"
                        f"&token={fake_secret}&X-Amz-Signature={fake_secret}#section"
                    ),
                )
            )
            note = Path(str(result["path"])).read_text(encoding="utf-8")
            serialized = repr(result)

            self.assertNotIn(fake_secret, note)
            self.assertNotIn(fake_secret, serialized)
            self.assertNotIn("user:pass", note)
            self.assertIn(
                'source_url: "https://example.com/story/?utm_source=test&ok=1#section"',
                note,
            )
            self.assertIn('canonical_url: "https://example.com/story/?ok=1"', note)
            self.assertIn("source_url_redacted: true", note)
            self.assertTrue(result["source_url_redacted"])

    def test_sensitive_query_key_families_are_removed(self) -> None:
        fake_secret = "test-only-secret"
        safe = save_capture.sanitize_url(
            "https://example.com/a?ok=1"
            f"&api_key={fake_secret}"
            f"&refreshToken={fake_secret}"
            f"&client_secret_hint={fake_secret}"
            f"&newPassword={fake_secret}"
            f"&X-Goog-Credential={fake_secret}"
        )

        self.assertEqual(safe.source_url, "https://example.com/a?ok=1")
        self.assertEqual(safe.canonical_url, "https://example.com/a?ok=1")
        self.assertTrue(safe.redacted)
        self.assertNotIn(fake_secret, repr(safe))

    def test_urls_that_only_differ_by_token_share_source_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first = save_capture.run_capture(
                make_args(
                    temp_dir,
                    url="https://example.com/item?token=one&ok=1",
                    title="First title",
                )
            )
            second = save_capture.run_capture(
                make_args(
                    temp_dir,
                    url="https://example.com/item?token=two&ok=1",
                    title="Different title",
                )
            )

            self.assertEqual(first["status"], "created")
            self.assertEqual(second["status"], "duplicate")
            self.assertEqual(first["source_id"], second["source_id"])
            self.assertEqual(first["path"], second["path"])

    def test_missing_tavily_key_reports_configuration_cause(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.dict(
            save_capture.os.environ, {}, clear=True
        ):
            result = save_capture.run_capture(
                make_args(temp_dir, tavily="auto", dry_run=True)
            )

        self.assertTrue(result["link_only"])
        self.assertTrue(
            any("TAVILY_API_KEY" in warning for warning in result["warnings"]),
            result["warnings"],
        )

    def test_redacted_url_is_never_sent_to_tavily(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_secret = "test-only-signature"
            with mock.patch.object(
                save_capture,
                "extract_with_tavily",
                side_effect=AssertionError("Tavily must not be called"),
            ) as extract:
                result = save_capture.run_capture(
                    make_args(
                        temp_dir,
                        url=f"https://example.com/private?X-Amz-Signature={fake_secret}",
                        tavily="auto",
                    )
                )

            extract.assert_not_called()
            self.assertNotIn(fake_secret, repr(result))
            self.assertTrue(result["source_url_redacted"])

    def test_selection_only_capture_does_not_trigger_tavily_auto(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            selection_file = Path(temp_dir) / "selection.txt"
            selection_file.write_text("Đoạn đã chọn.", encoding="utf-8")
            with mock.patch.object(
                save_capture,
                "extract_with_tavily",
                side_effect=AssertionError("Tavily must not be called"),
            ) as extract:
                result = save_capture.run_capture(
                    make_args(
                        temp_dir,
                        selection_file=str(selection_file),
                        capture_method="selection",
                        tavily="auto",
                    )
                )

            extract.assert_not_called()
            self.assertEqual(result["capture_method"], "selection")

    def test_explicit_tavily_depth_supplements_existing_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            content_file = Path(temp_dir) / "content.txt"
            content_file.write_text("browser " * 100, encoding="utf-8")
            extracted = save_capture.TavilyResult(
                content="extracted " * 120,
                depth="basic",
                request_id="request-fixture",
            )
            with mock.patch.object(
                save_capture, "extract_with_tavily", return_value=extracted
            ) as extract:
                result = save_capture.run_capture(
                    make_args(
                        temp_dir,
                        content_file=str(content_file),
                        allow_text_only=True,
                        tavily="basic",
                    )
                )

            extract.assert_called_once_with(
                "https://example.com/story/?utm_source=test&b=2&a=1#section",
                "basic",
                timeout=30.0,
            )
            self.assertEqual(result["capture_method"], "hybrid")

    def test_tavily_http_boundary_builds_request_and_parses_success(self) -> None:
        response = FakeHttpResponse(
            json.dumps(
                {
                    "request_id": "request-http-fixture",
                    "results": [{"raw_content": "Extracted content"}],
                    "failed_results": [],
                }
            ).encode("utf-8")
        )
        with mock.patch.dict(
            save_capture.os.environ, {"TAVILY_API_KEY": "test-api-key"}, clear=True
        ), mock.patch.object(
            save_capture.urllib.request, "urlopen", return_value=response
        ) as urlopen:
            result = save_capture.extract_with_tavily(
                "https://example.com/item?ok=1", "advanced", timeout=7.5
            )

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(urlopen.call_args.kwargs, {"timeout": 7.5})
        self.assertEqual(request.full_url, "https://api.tavily.com/extract")
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-api-key")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(request.get_header("User-agent"), "web-to-obsidian/0.3.0")
        self.assertEqual(
            payload,
            {
                "urls": "https://example.com/item?ok=1",
                "extract_depth": "advanced",
                "format": "markdown",
                "include_images": False,
                "include_favicon": False,
                "include_usage": True,
            },
        )
        self.assertEqual(result.content, "Extracted content")
        self.assertEqual(result.depth, "advanced")
        self.assertEqual(result.request_id, "request-http-fixture")

    def test_capture_sends_normalized_safe_url_at_tavily_http_boundary(self) -> None:
        response = FakeHttpResponse(
            json.dumps(
                {
                    "request_id": "request-normalized-fixture",
                    "results": [{"raw_content": "extracted " * 80}],
                }
            ).encode("utf-8")
        )
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.dict(
            save_capture.os.environ, {"TAVILY_API_KEY": "test-api-key"}, clear=True
        ), mock.patch.object(
            save_capture.urllib.request, "urlopen", return_value=response
        ) as urlopen:
            result = save_capture.run_capture(
                make_args(
                    temp_dir,
                    url="HTTPS://Example.COM:443/item?utm_source=mail&ok=1#fragment",
                    tavily="basic",
                )
            )

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(
            payload["urls"],
            "https://example.com/item?utm_source=mail&ok=1#fragment",
        )
        self.assertEqual(result["capture_method"], "tavily-basic")

    def test_tavily_failed_result_does_not_expose_upstream_error(self) -> None:
        marker = "upstream-secret-marker"
        response = FakeHttpResponse(
            json.dumps({"results": [], "failed_results": [{"error": marker}]}).encode(
                "utf-8"
            )
        )
        with mock.patch.dict(
            save_capture.os.environ, {"TAVILY_API_KEY": "test-api-key"}, clear=True
        ), mock.patch.object(
            save_capture.urllib.request, "urlopen", return_value=response
        ):
            with self.assertRaises(save_capture.CaptureError) as raised:
                save_capture.extract_with_tavily(
                    "https://example.com/item", "basic", timeout=3.0
                )

        self.assertNotIn(marker, str(raised.exception))
        self.assertEqual(str(raised.exception), "Tavily could not extract this URL.")

    def test_tavily_network_and_http_errors_are_value_free(self) -> None:
        marker = "external-secret-marker"
        cases = [
            urllib.error.URLError(marker),
            urllib.error.HTTPError(
                "https://api.tavily.com/extract",
                503,
                marker,
                {},
                io.BytesIO(marker.encode("utf-8")),
            ),
        ]
        for error in cases:
            with self.subTest(error=type(error).__name__), mock.patch.dict(
                save_capture.os.environ, {"TAVILY_API_KEY": "test-api-key"}, clear=True
            ), mock.patch.object(
                save_capture.urllib.request, "urlopen", side_effect=error
            ):
                with self.assertRaises(save_capture.CaptureError) as raised:
                    save_capture.extract_with_tavily(
                        "https://example.com/item", "basic", timeout=3.0
                    )
                self.assertNotIn(marker, str(raised.exception))

    def test_tavily_malformed_json_is_a_generic_error(self) -> None:
        response = FakeHttpResponse(b"not-json-secret-marker")
        with mock.patch.dict(
            save_capture.os.environ, {"TAVILY_API_KEY": "test-api-key"}, clear=True
        ), mock.patch.object(
            save_capture.urllib.request, "urlopen", return_value=response
        ):
            with self.assertRaises(save_capture.CaptureError) as raised:
                save_capture.extract_with_tavily(
                    "https://example.com/item", "basic", timeout=3.0
                )

        self.assertNotIn("secret-marker", str(raised.exception))
        self.assertEqual(
            str(raised.exception),
            "Tavily extraction returned an invalid or timed-out response.",
        )

    def test_shorter_tavily_success_records_request_without_changing_capture_method(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            content_file = Path(temp_dir) / "content.txt"
            content_file.write_text("browser " * 100, encoding="utf-8")
            extracted = save_capture.TavilyResult(
                content="short",
                depth="basic",
                request_id="request-short-fixture",
            )
            with mock.patch.object(
                save_capture, "extract_with_tavily", return_value=extracted
            ):
                result = save_capture.run_capture(
                    make_args(
                        temp_dir,
                        content_file=str(content_file),
                        allow_text_only=True,
                        tavily="basic",
                    )
                )

            note = Path(str(result["path"])).read_text(encoding="utf-8")
            self.assertEqual(result["capture_method"], "chrome")
            self.assertIn('tavily_request_id: "request-short-fixture"', note)
            self.assertNotIn("## Nội dung nguồn\n\nshort", note)

    def test_creates_utf8_note_and_detects_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            content_file = Path(temp_dir) / "capture.txt"
            content_file.write_text("Nội dung được giữ nguyên.", encoding="utf-8")
            args = make_args(temp_dir, content_file=str(content_file), allow_text_only=True)

            first = save_capture.run_capture(args)
            self.assertEqual(first["status"], "created")
            note_path = Path(str(first["path"]))
            self.assertTrue(note_path.exists())
            note = note_path.read_text(encoding="utf-8")
            self.assertIn("canonical_url: \"https://example.com/story/?b=2&a=1\"", note)
            self.assertIn("canonicalization_version: 2", note)
            self.assertIn("Nội dung được giữ nguyên.", note)

            second = save_capture.run_capture(args)
            self.assertEqual(second["status"], "duplicate")
            self.assertEqual(Path(str(second["path"])), note_path)

    def test_created_note_enables_web_clip_css_class(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = save_capture.run_capture(make_args(temp_dir))
            note = Path(str(result["path"])).read_text(encoding="utf-8")
            frontmatter = yaml.safe_load(note.split("---", 2)[1])

            self.assertEqual(frontmatter.get("cssclasses"), ["web-clip"])

    def test_additional_cssclasses_are_opt_in_deduplicated_and_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = save_capture.run_capture(
                make_args(
                    temp_dir,
                    cssclass=["wide", "web-clip", "img-grid", "wide"],
                )
            )
            note = Path(str(result["path"])).read_text(encoding="utf-8")
            frontmatter = yaml.safe_load(note.split("---", 2)[1])

            self.assertEqual(
                frontmatter.get("cssclasses"),
                ["web-clip", "wide", "img-grid"],
            )

    def test_invalid_cssclass_is_rejected_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(save_capture.CaptureError, "CSS class"):
                save_capture.run_capture(
                    make_args(temp_dir, cssclass=["wide]\\nsource_url: evil"])
                )

            self.assertEqual(list(Path(temp_dir).rglob("*.md")), [])

    def test_link_only_capture_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = save_capture.run_capture(
                make_args(temp_dir, title="Bookmark", content_type="bookmark")
            )
            self.assertTrue(result["link_only"])
            note = Path(str(result["path"])).read_text(encoding="utf-8")
            self.assertIn("link_only: true", note)
            self.assertIn("Link-only capture", note)

    def test_destination_cannot_escape_vault(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(save_capture.CaptureError):
                save_capture.run_capture(make_args(temp_dir, folder="../outside"))

    def test_resolve_within_retries_a_transient_outside_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir).resolve()
            destination = vault / "00 Inbox" / "Web"
            transient_outside = vault.parent / "transient-outside"
            path_type = type(destination)
            original_resolve = path_type.resolve
            transient_results = 0

            def unstable_resolve(path: Path, strict: bool = False) -> Path:
                nonlocal transient_results
                if path == destination and transient_results == 0:
                    transient_results += 1
                    return transient_outside
                return original_resolve(path, strict=strict)

            with mock.patch.object(
                path_type,
                "resolve",
                autospec=True,
                side_effect=unstable_resolve,
            ):
                try:
                    result = save_capture.run_capture(
                        make_args(temp_dir, dry_run=True)
                    )
                except save_capture.CaptureError as exc:
                    self.fail(f"Transient path resolution escaped the vault: {exc}")

            self.assertEqual(result["status"], "dry-run")
            self.assertEqual(transient_results, 1)

    def test_existing_base_and_suffix_files_are_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination_folder = Path(temp_dir) / "00 Inbox" / "Web"
            destination_folder.mkdir(parents=True)
            base = destination_folder / "2026-09-13 - Collision.md"
            suffix = destination_folder / "2026-09-13 - Collision - 3aecda.md"
            base.write_text("preserve base", encoding="utf-8")
            suffix.write_text("preserve suffix", encoding="utf-8")

            result = save_capture.run_capture(
                make_args(
                    temp_dir,
                    url="https://example.com/collision",
                    title="Collision",
                )
            )

            self.assertEqual(base.read_text(encoding="utf-8"), "preserve base")
            self.assertEqual(suffix.read_text(encoding="utf-8"), "preserve suffix")
            self.assertTrue(str(result["path"]).endswith("Collision - 3aecda-2.md"))

    def test_publish_fails_closed_when_hard_links_are_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(
                save_capture.os, "link", side_effect=OSError("unsupported fixture")
            ):
                with self.assertRaisesRegex(
                    save_capture.CaptureError, "without overwrite risk"
                ):
                    save_capture.run_capture(make_args(temp_dir, title="No hard links"))

            self.assertEqual(list(Path(temp_dir).rglob("*.md")), [])
            self.assertEqual(list(Path(temp_dir).rglob("*.tmp")), [])

    def test_concurrent_capture_of_same_source_with_different_titles_creates_one_note(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_find_duplicate = save_capture.find_duplicate
            barrier = threading.Barrier(2)
            call_lock = threading.Lock()
            initial_calls = 0

            def synchronized_find_duplicate(*args: object, **kwargs: object) -> object:
                nonlocal initial_calls
                result = original_find_duplicate(*args, **kwargs)
                should_wait = False
                with call_lock:
                    if initial_calls < 2 and result is None:
                        initial_calls += 1
                        should_wait = True
                if should_wait:
                    barrier.wait(timeout=5)
                return result

            arguments = [
                make_args(temp_dir, title="Concurrent A"),
                make_args(temp_dir, title="Concurrent B"),
            ]
            with mock.patch.object(
                save_capture, "find_duplicate", side_effect=synchronized_find_duplicate
            ):
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    results = list(executor.map(save_capture.run_capture, arguments))

            self.assertEqual(sorted(result["status"] for result in results), ["created", "duplicate"])
            notes = list(Path(temp_dir).glob("00 Inbox/Web/*.md"))
            self.assertEqual(len(notes), 1)

    def test_concurrent_same_source_across_folders_uses_one_identity_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_find_duplicate = save_capture.find_duplicate
            barrier = threading.Barrier(2)
            call_lock = threading.Lock()
            initial_calls = 0

            def synchronized_find_duplicate(*args: object, **kwargs: object) -> object:
                nonlocal initial_calls
                result = original_find_duplicate(*args, **kwargs)
                should_wait = False
                with call_lock:
                    if initial_calls < 2 and result is None:
                        initial_calls += 1
                        should_wait = True
                if should_wait:
                    barrier.wait(timeout=5)
                return result

            arguments = [
                make_args(temp_dir, title="Folder A", folder="Inbox/A"),
                make_args(temp_dir, title="Folder B", folder="Inbox/B"),
            ]
            with mock.patch.object(
                save_capture, "find_duplicate", side_effect=synchronized_find_duplicate
            ):
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    results = list(executor.map(save_capture.run_capture, arguments))

            self.assertEqual(
                sorted(result["status"] for result in results),
                ["created", "duplicate"],
            )
            self.assertEqual(len(list(Path(temp_dir).rglob("*.md"))), 1)

    def test_identity_lock_timeout_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "00 Inbox" / "Web"
            lock_directory = Path(temp_dir) / ".web-to-obsidian-locks"
            lock_directory.mkdir(parents=True)
            (lock_directory / "8a07317f666f7fd8.lock").write_text(
                "other-writer", encoding="utf-8"
            )

            with mock.patch("time.monotonic", side_effect=[0.0, 11.0]), mock.patch(
                "time.sleep"
            ):
                with self.assertRaisesRegex(
                    save_capture.CaptureError, "still in progress"
                ):
                    save_capture.run_capture(
                        make_args(
                            temp_dir,
                            url="https://example.com/locked",
                            title="Locked",
                        )
                    )

            self.assertEqual(list(destination.glob("*.md")), [])

    def test_two_processes_with_same_source_and_different_titles_create_one_note(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            context = multiprocessing.get_context("spawn")
            start_event = context.Event()
            result_queue = context.Queue()
            processes = [
                context.Process(
                    target=capture_in_process,
                    args=(temp_dir, title, start_event, result_queue),
                )
                for title in ("Process title A", "Process title B")
            ]
            for process in processes:
                process.start()
            start_event.set()
            for process in processes:
                process.join(timeout=15.0)

            self.assertEqual([process.exitcode for process in processes], [0, 0])
            results = [result_queue.get(timeout=5.0) for _ in processes]
            self.assertNotIn("error_type", results[0])
            self.assertNotIn("error_type", results[1])
            self.assertEqual(
                sorted(result["status"] for result in results),
                ["created", "duplicate"],
            )
            self.assertEqual(results[0]["path"], results[1]["path"])
            self.assertEqual(len(list(Path(temp_dir).rglob("*.md"))), 1)

    def test_v2_notes_keep_trailing_slash_identity_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            without_slash = save_capture.run_capture(
                make_args(
                    temp_dir,
                    url="https://example.com/story",
                    title="No slash",
                )
            )
            with_slash = save_capture.run_capture(
                make_args(
                    temp_dir,
                    url="https://example.com/story/",
                    title="With slash",
                )
            )

            self.assertEqual(without_slash["status"], "created")
            self.assertEqual(with_slash["status"], "created")
            self.assertNotEqual(without_slash["source_id"], with_slash["source_id"])

    def test_v2_notes_keep_query_order_identity_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sorted_query = save_capture.run_capture(
                make_args(
                    temp_dir,
                    url="https://example.com/story?a=1&b=2",
                    title="Sorted query",
                )
            )
            reversed_query = save_capture.run_capture(
                make_args(
                    temp_dir,
                    url="https://example.com/story?b=2&a=1",
                    title="Reversed query",
                )
            )

            self.assertEqual(sorted_query["status"], "created")
            self.assertEqual(reversed_query["status"], "created")
            self.assertNotEqual(sorted_query["source_id"], reversed_query["source_id"])

    def test_v2_canonicalization_detects_legacy_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            old_note = Path(temp_dir) / "old.md"
            old_note.write_text(
                "---\n"
                "type: source\n"
                'source_id: "77c932cb469c6544"\n'
                'source_url: "https://example.com/story/?b=2&a=1"\n'
                'canonical_url: "https://example.com/story?a=1&b=2"\n'
                "---\n",
                encoding="utf-8",
            )

            result = save_capture.run_capture(
                make_args(
                    temp_dir,
                    url="https://Example.COM/story/?b=2&a=1",
                )
            )

            self.assertEqual(result["status"], "duplicate")
            self.assertEqual(Path(str(result["path"])), old_note.resolve())

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
            args = make_args(temp_dir, content_file=str(content_file), allow_text_only=True)
            result = save_capture.run_capture(args)
            note = Path(str(result["path"])).read_text(encoding="utf-8")
            self.assertIn("> [!toc]- Table of contents", note)
            self.assertIn("> - [[#Intro]]", note)
            self.assertIn(">   - [[#Intro#First section|First section]]", note)
            self.assertIn(">   - [[#Intro#Second section|Second section]]", note)
            self.assertIn(
                ">     - [[#Intro#Second section#Second section detail|Second section detail]]",
                note,
            )

    def test_content_file_capture_with_fewer_than_three_headings_gets_no_toc(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            content_file = Path(temp_dir) / "capture.md"
            content_file.write_text(
                "# Intro\n\nSome intro text.\n\n## Only other heading\n\nBody.\n",
                encoding="utf-8",
            )
            args = make_args(temp_dir, content_file=str(content_file), allow_text_only=True)
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


if __name__ == "__main__":
    unittest.main()
