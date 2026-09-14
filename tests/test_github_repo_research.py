from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "github-repo-research"
    / "scripts"
    / "search_github_repos.py"
)
SPEC = importlib.util.spec_from_file_location("search_github_repos", SCRIPT_PATH)
assert SPEC and SPEC.loader
search = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = search
SPEC.loader.exec_module(search)


class GitHubRepoResearchTests(unittest.TestCase):
    def test_normalizes_repository_paths_and_rejects_non_repositories(self) -> None:
        self.assertEqual(
            search.normalize_repository_url("https://github.com/Owner/Repo/tree/main/docs?q=1#readme"),
            ("Owner/Repo", "https://github.com/Owner/Repo"),
        )
        self.assertEqual(
            search.normalize_repository_url("https://github.com/owner/repo.git"),
            ("owner/repo", "https://github.com/owner/repo"),
        )
        self.assertIsNone(search.normalize_repository_url("https://github.com/topics/rag"))
        self.assertIsNone(search.normalize_repository_url("https://example.com/owner/repo"))

    def test_collects_and_deduplicates_results_across_queries(self) -> None:
        responses = [
            {
                "request_id": "one",
                "results": [
                    {
                        "title": "Repo A",
                        "url": "https://github.com/acme/repo-a",
                        "content": "First snippet",
                        "score": 0.7,
                    },
                    {"title": "Topics", "url": "https://github.com/topics/agents", "score": 0.9},
                ],
            },
            {
                "request_id": "two",
                "results": [
                    {
                        "title": "Repo A better match",
                        "url": "https://github.com/ACME/repo-a/tree/main",
                        "content": "Better snippet",
                        "score": 0.9,
                    }
                ],
            },
        ]
        with mock.patch.object(search, "search_tavily", side_effect=responses):
            result = search.collect_repositories(
                ["query one", "query two"],
                search_depth="basic",
                max_results=8,
                include_raw_content=False,
                timeout=30.0,
            )

        self.assertEqual(len(result["repositories"]), 1)
        repository = result["repositories"][0]
        self.assertEqual(repository["repository"], "acme/repo-a")
        self.assertEqual(repository["snippet"], "Better snippet")
        self.assertEqual(repository["matched_queries"], ["query one", "query two"])

    def test_markdown_preserves_unicode(self) -> None:
        markdown = search.render_markdown({
            "searched_at": "2026-09-13T00:00:00+00:00",
            "search_depth": "basic",
            "queries": ["tóm tắt"],
            "repositories": [{
                "repository": "acme/repo",
                "url": "https://github.com/acme/repo",
                "title": "Công cụ 🔧",
                "snippet": "Tóm tắt tiếng Việt",
                "score": 0.5,
                "matched_queries": ["tóm tắt"],
                "raw_content": None,
            }],
        })
        self.assertIn("Công cụ 🔧", markdown)
        self.assertIn("Tóm tắt tiếng Việt", markdown)

    def test_loads_tavily_key_from_dotenv(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text('TAVILY_API_KEY="from-file"\n', encoding="utf-8")
            with mock.patch.dict(search.os.environ, {}, clear=True):
                loaded = search.load_dotenv(workspace=Path(temp_dir))
                self.assertEqual(loaded, env_path.resolve())
                self.assertEqual(search.os.environ["TAVILY_API_KEY"], "from-file")

    def test_missing_key_has_safe_error(self) -> None:
        with mock.patch.dict(search.os.environ, {}, clear=True):
            with self.assertRaisesRegex(search.SearchError, "TAVILY_API_KEY"):
                search.search_tavily(
                    "test", search_depth="basic", max_results=5,
                    include_raw_content=False, timeout=1,
                )


if __name__ == "__main__":
    unittest.main()
