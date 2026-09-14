#!/usr/bin/env python3
"""Search public GitHub repositories through Tavily and emit normalized evidence."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_URL = "https://api.tavily.com/search"
ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
NON_REPOSITORY_ROOTS = {
    "about", "apps", "collections", "contact", "customer-stories", "enterprise",
    "events", "explore", "features", "issues", "login", "marketplace", "new",
    "notifications", "organizations", "orgs", "pricing", "pulls", "search",
    "security", "settings", "signup", "site", "sponsors", "topics", "trending", "users",
}


class SearchError(RuntimeError):
    """A safe, user-facing search failure."""


def _dotenv_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
        return value[1:-1]
    comment = re.search(r"\s+#", value)
    if comment:
        value = value[: comment.start()].rstrip()
    return value


def load_dotenv(path_value: str | None = None, *, workspace: Path | None = None) -> Path | None:
    """Load a local .env without overriding variables already in the process."""

    env_path = Path(path_value).expanduser() if path_value else (workspace or Path.cwd()) / ".env"
    if not env_path.is_absolute():
        env_path = (workspace or Path.cwd()) / env_path
    env_path = env_path.resolve()
    if not env_path.exists():
        if path_value:
            raise SearchError(f"Environment file does not exist: {env_path}")
        return None
    if not env_path.is_file():
        raise SearchError(f"Environment file is not a file: {env_path}")

    for line_number, raw_line in enumerate(env_path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise SearchError(f"Invalid .env assignment at {env_path}:{line_number}")
        name, raw_value = line.split("=", 1)
        name = name.strip()
        if not ENV_NAME_PATTERN.fullmatch(name):
            raise SearchError(f"Invalid .env variable name at {env_path}:{line_number}")
        os.environ.setdefault(name, _dotenv_value(raw_value))
    return env_path


@dataclass
class RepositoryResult:
    repository: str
    url: str
    title: str
    snippet: str
    score: float | None
    matched_queries: list[str] = field(default_factory=list)
    raw_content: str | None = None


def normalize_repository_url(value: str) -> tuple[str, str] | None:
    """Return (owner/repo, canonical URL) for a public github.com repository URL."""
    try:
        parsed = urllib.parse.urlsplit(value.strip())
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"}:
        return None
    if (parsed.hostname or "").lower().rstrip(".") != "github.com":
        return None

    parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0].lower() in NON_REPOSITORY_ROOTS:
        return None
    owner = parts[0].strip()
    repository = parts[1].strip()
    if repository.lower().endswith(".git"):
        repository = repository[:-4]
    if not owner or not repository or owner in {".", ".."} or repository in {".", ".."}:
        return None
    if any(character.isspace() for character in owner + repository):
        return None

    name = f"{owner}/{repository}"
    return name, f"https://github.com/{name}"


def _error_detail(body: bytes) -> str:
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ""
    detail = value.get("detail") if isinstance(value, dict) else None
    if isinstance(detail, dict):
        detail = detail.get("error")
    return str(detail or "").strip()


def search_tavily(
    query: str,
    *,
    search_depth: str,
    max_results: int,
    include_raw_content: bool,
    timeout: float,
) -> dict[str, Any]:
    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        raise SearchError("TAVILY_API_KEY is not set in the environment.")

    payload = {
        "query": query,
        "topic": "general",
        "search_depth": search_depth,
        "chunks_per_source": 3,
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": "markdown" if include_raw_content else False,
        "include_images": False,
        "include_favicon": False,
        "include_domains": ["github.com"],
        "include_domains_mode": "filter",
        "include_usage": True,
        "safe_search": True,
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "web-to-obsidian/0.2.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = _error_detail(exc.read())
        suffix = f": {detail}" if detail else ""
        raise SearchError(f"Tavily search failed with HTTP {exc.code}{suffix}.") from exc
    except urllib.error.URLError as exc:
        raise SearchError(f"Tavily search could not connect: {exc.reason}.") from exc
    except (TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SearchError("Tavily search returned an invalid or timed-out response.") from exc


def collect_repositories(
    queries: list[str],
    *,
    search_depth: str,
    max_results: int,
    include_raw_content: bool,
    timeout: float,
) -> dict[str, Any]:
    repositories: dict[str, RepositoryResult] = {}
    requests: list[dict[str, Any]] = []

    for query in queries:
        response = search_tavily(
            query,
            search_depth=search_depth,
            max_results=max_results,
            include_raw_content=include_raw_content,
            timeout=timeout,
        )
        requests.append({
            "query": query,
            "request_id": response.get("request_id"),
            "response_time": response.get("response_time"),
            "usage": response.get("usage"),
        })
        for item in response.get("results") or []:
            if not isinstance(item, dict):
                continue
            normalized = normalize_repository_url(str(item.get("url") or ""))
            if not normalized:
                continue
            name, url = normalized
            try:
                score = float(item["score"]) if item.get("score") is not None else None
            except (TypeError, ValueError):
                score = None
            candidate = RepositoryResult(
                repository=name,
                url=url,
                title=str(item.get("title") or name).strip(),
                snippet=str(item.get("content") or "").strip(),
                score=score,
                matched_queries=[query],
                raw_content=(str(item.get("raw_content") or "").strip() or None),
            )
            key = name.casefold()
            existing = repositories.get(key)
            if existing is None:
                repositories[key] = candidate
                continue
            if query not in existing.matched_queries:
                existing.matched_queries.append(query)
            if candidate.score is not None and (existing.score is None or candidate.score > existing.score):
                existing.title = candidate.title
                existing.snippet = candidate.snippet
                existing.score = candidate.score
                existing.raw_content = candidate.raw_content

    ordered = sorted(
        repositories.values(),
        key=lambda item: (item.score is not None, item.score or 0.0, len(item.matched_queries)),
        reverse=True,
    )
    return {
        "searched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "search_depth": search_depth,
        "domain_filter": ["github.com"],
        "queries": queries,
        "requests": requests,
        "repositories": [asdict(item) for item in ordered],
    }


def render_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# GitHub repository search evidence", "",
        f"- Searched at: {data['searched_at']}",
        f"- Search depth: {data['search_depth']}",
        "- Domain filter: `github.com`", "- Queries:",
        *[f"  - {query}" for query in data["queries"]], "", "## Repositories",
    ]
    repositories = data["repositories"]
    if not repositories:
        lines.extend(["", "No repository roots were found."])
    for index, item in enumerate(repositories, start=1):
        score = "unknown" if item["score"] is None else f"{item['score']:.4f}"
        lines.extend([
            "", f"### {index}. [{item['repository']}]({item['url']})", "",
            f"- Search title: {item['title']}",
            f"- Tavily relevance: {score}",
            f"- Matched queries: {', '.join(item['matched_queries'])}", "",
            item["snippet"] or "_No snippet returned._",
        ])
        if item.get("raw_content"):
            lines.extend(["", "<details><summary>Raw content</summary>", "", item["raw_content"], "", "</details>"])
    return "\n".join(lines).rstrip() + "\n"


def _write_output(path_value: str, content: str, *, force: bool) -> None:
    path = Path(path_value).expanduser().resolve()
    if path.exists() and not force:
        raise SearchError(f"Output already exists: {path}. Use --force to replace it.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=path.parent,
            prefix=f".{path.name}-", suffix=".tmp", delete=False,
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, path)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", action="append", required=True, help="Focused search query; repeat up to three times")
    parser.add_argument(
        "--env-file",
        help="Optional .env path; defaults to .env in the current working directory",
    )
    parser.add_argument("--search-depth", choices=("basic", "advanced"), default="basic")
    parser.add_argument("--max-results", type=int, default=8, help="Results per query (1-20)")
    parser.add_argument("--include-raw-content", action="store_true")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", help="Optional UTF-8 output path; stdout when omitted")
    parser.add_argument("--force", action="store_true", help="Replace an existing --output file")
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser


def _configure_utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    _configure_utf8_console()
    args = build_parser().parse_args()
    queries = [query.strip() for query in args.query if query.strip()]
    try:
        load_dotenv(args.env_file, workspace=Path.cwd())
        if not queries:
            raise SearchError("At least one non-empty --query is required.")
        if len(queries) > 3:
            raise SearchError("Use at most three --query values per run.")
        if not 1 <= args.max_results <= 20:
            raise SearchError("--max-results must be between 1 and 20.")
        if args.timeout <= 0:
            raise SearchError("--timeout must be greater than zero.")
        data = collect_repositories(
            queries,
            search_depth=args.search_depth,
            max_results=args.max_results,
            include_raw_content=args.include_raw_content,
            timeout=args.timeout,
        )
        content = render_markdown(data) if args.format == "markdown" else json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            _write_output(args.output, content, force=args.force)
            print(json.dumps({
                "status": "created",
                "path": str(Path(args.output).expanduser().resolve()),
                "repositories": len(data["repositories"]),
            }, ensure_ascii=False))
        else:
            print(content, end="")
    except (SearchError, OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
