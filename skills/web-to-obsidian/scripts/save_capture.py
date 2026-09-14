#!/usr/bin/env python3
"""Create a duplicate-safe Obsidian source note from browser or Tavily content.

The script uses only the Python standard library. It never accepts an API key
as an argument; optional Tavily extraction reads TAVILY_API_KEY from the
process environment or a local .env file.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


TRACKING_PARAMETERS = {
    "dclid",
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "mkt_tok",
    "ref_src",
    "si",
    "vero_conv",
    "vero_id",
}
SENSITIVE_QUERY_PARTS = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "code",
    "credential",
    "key",
    "password",
    "session",
    "sig",
    "signature",
    "token",
}
SKIP_DIRECTORIES = {".git", ".obsidian", ".trash", "node_modules", "__pycache__"}
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
CONTENT_TYPES = ("article", "news", "bookmark", "music", "video", "podcast", "social", "other")
CAPTURE_METHODS = ("selection", "chrome", "tavily-basic", "tavily-advanced", "hybrid", "manual")
ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class CaptureError(RuntimeError):
    """A safe, user-facing capture failure."""


@dataclass(frozen=True)
class TavilyResult:
    content: str
    depth: str
    request_id: str | None


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
            raise CaptureError(f"Environment file does not exist: {env_path}")
        return None
    if not env_path.is_file():
        raise CaptureError(f"Environment file is not a file: {env_path}")

    for line_number, raw_line in enumerate(env_path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise CaptureError(f"Invalid .env assignment at {env_path}:{line_number}")
        name, raw_value = line.split("=", 1)
        name = name.strip()
        if not ENV_NAME_PATTERN.fullmatch(name):
            raise CaptureError(f"Invalid .env variable name at {env_path}:{line_number}")
        os.environ.setdefault(name, _dotenv_value(raw_value))
    return env_path


def _vault_from_yaml(config_path: Path) -> str | None:
    if not config_path.is_file():
        return None
    for raw_line in config_path.read_text(encoding="utf-8-sig").splitlines():
        match = re.match(r"^\s*vault_root\s*:\s*(.*?)\s*$", raw_line)
        if not match:
            continue
        value = match.group(1).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
            value = value[1:-1]
        return value or None
    return None


def resolve_vault(vault_argument: str | None, *, workspace: Path | None = None) -> str:
    """Resolve CLI, environment, then workspace YAML configuration."""

    if vault_argument and vault_argument.strip():
        return vault_argument.strip()
    env_vault = os.environ.get("OBSIDIAN_VAULT_PATH", "").strip()
    if env_vault:
        return env_vault
    config_path = (workspace or Path.cwd()) / "web-to-obsidian.yaml"
    config_vault = _vault_from_yaml(config_path.resolve())
    if config_vault:
        return config_vault
    raise CaptureError(
        "Obsidian vault is not configured. Use --vault, set OBSIDIAN_VAULT_PATH in .env, "
        "or add vault_root to web-to-obsidian.yaml."
    )


def canonicalize_url(value: str) -> str:
    """Normalize a public URL and remove common tracking parameters."""

    raw = value.strip()
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise CaptureError("The source URL must be an absolute HTTP(S) URL.")

    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower().rstrip(".")
    try:
        hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise CaptureError("The source URL contains an invalid hostname.") from exc

    port = parsed.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{hostname}:{port}"
    else:
        netloc = hostname

    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"

    kept_query: list[tuple[str, str]] = []
    for key, item_value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        normalized_key = key.lower()
        if normalized_key.startswith("utm_") or normalized_key in TRACKING_PARAMETERS:
            continue
        kept_query.append((key, item_value))
    kept_query.sort(key=lambda item: (item[0].lower(), item[1]))
    query = urllib.parse.urlencode(kept_query, doseq=True)

    return urllib.parse.urlunsplit((scheme, netloc, path, query, ""))


def source_id_for(canonical_url: str) -> str:
    return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:16]


def sanitize_filename(title: str, fallback: str, max_length: int = 96) -> str:
    value = unicodedata.normalize("NFKC", title).strip()
    value = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "-", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"-{2,}", "-", value).strip(" .-")
    if not value:
        value = fallback
    if value.upper() in WINDOWS_RESERVED_NAMES:
        value = f"{value}-note"
    value = value[:max_length].rstrip(" .-")
    return value or fallback


def is_safe_public_url_for_tavily(value: str) -> tuple[bool, str | None]:
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        return False, "invalid URL"

    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return False, "only absolute HTTP(S) URLs are supported"
    if parsed.username or parsed.password:
        return False, "URL contains embedded credentials"

    host = parsed.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
        return False, "local or internal host"

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and not address.is_global:
        return False, "private or non-global IP address"

    for key, _ in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        normalized_key = key.lower()
        if normalized_key in SENSITIVE_QUERY_PARTS or any(part in normalized_key for part in ("token", "secret", "password")):
            return False, f"potentially sensitive query parameter: {key}"
    return True, None


def _read_optional_file(path_value: str | None) -> str:
    if not path_value:
        return ""
    if path_value == "-":
        return sys.stdin.read().strip()
    return Path(path_value).read_text(encoding="utf-8").strip()


def _yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _yaml_list(name: str, values: Iterable[str]) -> list[str]:
    cleaned = [value.strip() for value in values if value and value.strip()]
    if not cleaned:
        return [f"{name}: []"]
    return [f"{name}:", *[f"  - {_yaml_string(value)}" for value in cleaned]]


def _iter_markdown_files(vault: Path) -> Iterable[Path]:
    for root, directories, files in os.walk(vault):
        directories[:] = [name for name in directories if name not in SKIP_DIRECTORIES]
        root_path = Path(root)
        for filename in files:
            if filename.lower().endswith(".md"):
                yield root_path / filename


def find_duplicate(vault: Path, source_id: str, canonical_url: str) -> Path | None:
    id_pattern = re.compile(rf"(?m)^source_id:\s*[\"']?{re.escape(source_id)}[\"']?\s*$")
    canonical_pattern = re.compile(
        rf"(?m)^canonical_url:\s*[\"']?{re.escape(canonical_url)}[\"']?\s*$"
    )
    for note_path in _iter_markdown_files(vault):
        try:
            with note_path.open("r", encoding="utf-8") as handle:
                head = handle.read(32768)
        except (OSError, UnicodeError):
            continue
        if id_pattern.search(head) or canonical_pattern.search(head):
            return note_path
    return None


def extract_with_tavily(url: str, depth: str, timeout: float = 30.0) -> TavilyResult:
    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        raise CaptureError("TAVILY_API_KEY is not set in the environment.")

    payload = json.dumps(
        {
            "urls": url,
            "extract_depth": depth,
            "format": "markdown",
            "include_images": False,
            "include_favicon": False,
            "include_usage": True,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.tavily.com/extract",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "web-to-obsidian/0.1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise CaptureError(f"Tavily extraction failed with HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise CaptureError(f"Tavily extraction could not connect: {exc.reason}.") from exc
    except (TimeoutError, json.JSONDecodeError) as exc:
        raise CaptureError("Tavily extraction returned an invalid or timed-out response.") from exc

    results = data.get("results") or []
    if not results:
        failed = data.get("failed_results") or []
        message = "Tavily could not extract this URL."
        if failed and isinstance(failed[0], dict) and failed[0].get("error"):
            message = f"Tavily could not extract this URL: {failed[0]['error']}"
        raise CaptureError(message)

    content = str(results[0].get("raw_content") or "").strip()
    if not content:
        raise CaptureError("Tavily returned no page content.")
    return TavilyResult(content=content, depth=depth, request_id=data.get("request_id"))


def _within(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _render_note(
    *,
    title: str,
    content_type: str,
    source_id: str,
    source_url: str,
    canonical_url: str,
    author: str,
    published: str,
    captured: str,
    capture_method: str,
    platform: str,
    tags: list[str],
    topics: list[str],
    why: str,
    selection: str,
    summary: str,
    content: str,
    tavily_request_id: str | None,
) -> str:
    lines = [
        "---",
        "type: source",
        f"content_type: {content_type}",
        "status: inbox",
        f"source_id: {_yaml_string(source_id)}",
        f"title: {_yaml_string(title)}",
        f"source_url: {_yaml_string(source_url)}",
        f"canonical_url: {_yaml_string(canonical_url)}",
        f"author: {_yaml_string(author)}",
        f"published: {_yaml_string(published)}" if published else "published:",
        f"captured: {_yaml_string(captured)}",
        f"capture_method: {capture_method}",
        f"platform: {_yaml_string(platform)}",
        f"link_only: {'false' if content or selection else 'true'}",
    ]
    if tavily_request_id:
        lines.append(f"tavily_request_id: {_yaml_string(tavily_request_id)}")
    lines.extend(_yaml_list("tags", tags))
    lines.extend(_yaml_list("topics", topics))
    lines.extend(["---", "", f"# {title}", "", "> [!info] Nguồn", f"> [Mở liên kết gốc]({source_url})"])

    if why:
        lines.extend(["", "## Vì sao tôi lưu", "", why])
    if selection:
        quoted = "\n".join(f"> {line}" if line else ">" for line in selection.splitlines())
        lines.extend(["", "## Đoạn đã chọn", "", quoted])
    if summary:
        lines.extend(["", "## Tóm tắt", "", summary])
    if content:
        lines.extend(["", "## Nội dung nguồn", "", content])
    if not content and not selection:
        lines.extend(["", "> [!warning] Link-only capture", "> Không lấy được nội dung trang tại thời điểm lưu."])
    lines.extend(["", "## Ghi chú của tôi", ""])
    return "\n".join(lines).rstrip() + "\n"


def run_capture(args: argparse.Namespace) -> dict[str, object]:
    vault = Path(args.vault).expanduser().resolve()
    if not vault.is_dir():
        raise CaptureError(f"Vault does not exist or is not a directory: {vault}")

    canonical_url = canonicalize_url(args.url)
    source_id = source_id_for(canonical_url)
    duplicate = find_duplicate(vault, source_id, canonical_url)
    if duplicate:
        return {
            "status": "duplicate",
            "source_id": source_id,
            "canonical_url": canonical_url,
            "path": str(duplicate.resolve()),
        }

    content = _read_optional_file(args.content_file)
    selection = _read_optional_file(args.selection_file)
    had_browser_content = bool(content or selection)
    warnings: list[str] = []
    tavily_request_id: str | None = None
    tavily_depth: str | None = None

    needs_content = len(content) < args.min_content_chars
    if args.tavily != "off" and needs_content:
        safe, reason = is_safe_public_url_for_tavily(args.url)
        if not safe:
            warnings.append(f"Tavily skipped: {reason}.")
        else:
            depths = [args.tavily] if args.tavily in {"basic", "advanced"} else ["basic", "advanced"]
            last_error: CaptureError | None = None
            for depth in depths:
                try:
                    result = extract_with_tavily(args.url, depth, timeout=args.timeout)
                    if len(result.content) > len(content):
                        content = result.content
                        tavily_depth = result.depth
                        tavily_request_id = result.request_id
                    if len(content) >= args.min_content_chars:
                        break
                except CaptureError as exc:
                    last_error = exc
            if not tavily_depth and last_error:
                warnings.append(str(last_error))

    capture_method = args.capture_method
    if tavily_depth:
        if args.capture_method in {"chrome", "selection"} and had_browser_content:
            capture_method = "hybrid"
        else:
            capture_method = f"tavily-{tavily_depth}"

    parsed = urllib.parse.urlsplit(canonical_url)
    platform = args.platform.strip() if args.platform else parsed.hostname or ""
    captured = args.captured or datetime.now().astimezone().isoformat(timespec="seconds")
    title = args.title.strip() or platform or source_id
    filename_title = sanitize_filename(title, source_id)
    captured_date = captured[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", captured) else datetime.now().date().isoformat()

    destination_folder = (vault / args.folder).resolve()
    if not _within(vault, destination_folder):
        raise CaptureError("Destination folder must stay inside the vault.")

    filename = f"{captured_date} - {filename_title}.md"
    destination = destination_folder / filename
    if destination.exists():
        destination = destination_folder / f"{captured_date} - {filename_title} - {source_id[:6]}.md"
    if not _within(vault, destination.resolve()):
        raise CaptureError("Destination note must stay inside the vault.")

    tags = list(dict.fromkeys(["web-capture", f"source/{args.content_type}", *args.tag]))
    topics = list(dict.fromkeys(args.topic))
    note = _render_note(
        title=title,
        content_type=args.content_type,
        source_id=source_id,
        source_url=args.url.strip(),
        canonical_url=canonical_url,
        author=args.author.strip(),
        published=args.published.strip(),
        captured=captured,
        capture_method=capture_method,
        platform=platform,
        tags=tags,
        topics=topics,
        why=args.why.strip(),
        selection=selection,
        summary=args.summary.strip(),
        content=content,
        tavily_request_id=tavily_request_id,
    )

    if args.dry_run:
        return {
            "status": "dry-run",
            "source_id": source_id,
            "canonical_url": canonical_url,
            "capture_method": capture_method,
            "link_only": not bool(content or selection),
            "path": str(destination),
            "warnings": warnings,
        }

    destination_folder.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=destination_folder,
            prefix=f".{source_id}-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(note)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, destination)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()

    return {
        "status": "created",
        "source_id": source_id,
        "canonical_url": canonical_url,
        "capture_method": capture_method,
        "link_only": not bool(content or selection),
        "path": str(destination.resolve()),
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vault",
        help="Vault path; otherwise OBSIDIAN_VAULT_PATH or web-to-obsidian.yaml is used",
    )
    parser.add_argument(
        "--env-file",
        help="Optional .env path; defaults to .env in the current working directory",
    )
    parser.add_argument("--url", required=True, help="Original public or browser URL")
    parser.add_argument("--title", default="", help="Source title")
    parser.add_argument("--author", default="", help="Source author or artist")
    parser.add_argument("--published", default="", help="Publication or release date")
    parser.add_argument("--platform", default="", help="Source service; defaults to hostname")
    parser.add_argument("--content-type", choices=CONTENT_TYPES, default="bookmark")
    parser.add_argument("--capture-method", choices=CAPTURE_METHODS, default="manual")
    parser.add_argument("--content-file", help="UTF-8 file containing captured page content; use - for stdin")
    parser.add_argument("--selection-file", help="UTF-8 file containing the selected excerpt")
    parser.add_argument("--summary", default="", help="Optional user-approved summary")
    parser.add_argument("--why", default="", help="Why the user saved the source")
    parser.add_argument("--tag", action="append", default=[], help="Additional tag; repeat as needed")
    parser.add_argument("--topic", action="append", default=[], help="Topic; repeat as needed")
    parser.add_argument("--folder", default="00 Inbox/Web", help="Destination relative to vault root")
    parser.add_argument("--captured", default="", help="ISO timestamp; defaults to local current time")
    parser.add_argument("--tavily", choices=("off", "auto", "basic", "advanced"), default="off")
    parser.add_argument("--min-content-chars", type=int, default=400)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _configure_utf8_console() -> None:
    """Keep JSON output Unicode-safe on Windows legacy code pages."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    _configure_utf8_console()
    parser = build_parser()
    args = parser.parse_args()
    try:
        workspace = Path.cwd()
        load_dotenv(args.env_file, workspace=workspace)
        args.vault = resolve_vault(args.vault, workspace=workspace)
        result = run_capture(args)
    except (CaptureError, OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
