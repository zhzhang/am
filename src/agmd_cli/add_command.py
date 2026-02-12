"""Implementation for the `agmd add` command."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .sync_helpers import load_mappings, refresh_agents_files, write_mappings


def _find_project_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    return start


def _normalize_local_path(raw_path: str, project_root: Path) -> str:
    normalized_path = Path(raw_path)
    if not normalized_path.is_absolute():
        normalized_path = (project_root / normalized_path).resolve()

    try:
        relative_path = normalized_path.relative_to(project_root.resolve())
    except ValueError as exc:
        raise ValueError(
            f"Path '{raw_path}' must be within the project root '{project_root}'."
        ) from exc

    return "." if str(relative_path) == "." else relative_path.as_posix()


def _parse_github_path(github_path: str) -> tuple[str, str, list[str]]:
    cleaned = github_path.strip().strip("/")
    parts = [part for part in cleaned.split("/") if part]
    if len(parts) < 2:
        raise ValueError(
            f"Invalid GitHub path '{github_path}'. Expected at least <owner>/<repo>."
        )
    return parts[0], parts[1], parts[2:]


def _module_slug_directory_name(github_path: str) -> str:
    cleaned = github_path.strip().strip("/")
    if not cleaned:
        raise ValueError("GitHub path cannot be empty.")
    return re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned)


def _github_contents_api_url(owner: str, repo: str, path_in_repo: str) -> str:
    if path_in_repo:
        encoded_path = quote(path_in_repo, safe="/")
        return f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded_path}?ref=main"
    return f"https://api.github.com/repos/{owner}/{repo}/contents?ref=main"


def _fetch_json(url: str) -> object:
    request = Request(
        url,
        headers={
            "User-Agent": "agmd-cli/0.1",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:  # nosec B310
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Failed to fetch GitHub metadata from {url}. Error: {exc}"
        ) from exc


def _download_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "agmd-cli/0.1"})
    try:
        with urlopen(request, timeout=20) as response:  # nosec B310
            return response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ValueError(f"Failed to download file from {url}. Error: {exc}") from exc


def _download_github_module(github_path: str, destination_root: Path) -> int:
    owner, repo, repo_path_parts = _parse_github_path(github_path)
    module_path_in_repo = "/".join(repo_path_parts)
    module_slug = _module_slug_directory_name(github_path)
    module_destination = destination_root / ".agmd" / module_slug

    root_prefix = module_path_in_repo.strip("/")
    pending_paths = [root_prefix]
    file_count = 0

    while pending_paths:
        current_path = pending_paths.pop()
        payload = _fetch_json(
            _github_contents_api_url(owner=owner, repo=repo, path_in_repo=current_path)
        )
        entries = payload if isinstance(payload, list) else [payload]

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            entry_type = entry.get("type")
            entry_path = entry.get("path")
            if not isinstance(entry_path, str):
                continue

            if entry_type == "dir":
                pending_paths.append(entry_path)
                continue

            if entry_type != "file":
                continue

            download_url = entry.get("download_url")
            if not isinstance(download_url, str) or not download_url:
                continue

            if root_prefix:
                relative_part = (
                    entry_path.removeprefix(root_prefix).lstrip("/")
                    if entry_path.startswith(root_prefix)
                    else Path(entry_path).name
                )
            else:
                relative_part = entry_path

            destination_path = module_destination / Path(relative_part)
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            destination_path.write_bytes(_download_bytes(download_url))
            file_count += 1

    if file_count == 0:
        raise ValueError(f"No files found at GitHub path '{github_path}'.")
    return file_count


def register_add_command(subparsers: argparse._SubParsersAction) -> None:
    add_parser = subparsers.add_parser(
        "add",
        help="Add a GitHub slug and refresh AGENTS.md files.",
    )
    add_parser.add_argument(
        "github_path",
        help="GitHub slug (owner/repo[/path]).",
    )
    add_parser.add_argument(
        "--path",
        default=".",
        metavar="PATH",
        help="Project path where AGENTS.md should be materialized (default: root).",
    )
    add_parser.add_argument(
        "--module",
        action="store_true",
        help=(
            "Download every file from the GitHub path into "
            "<path>/.agmd/<github-path-slug>/..."
        ),
    )
    add_parser.set_defaults(handler=run_add_command)


def run_add_command(args: argparse.Namespace) -> int:
    project_root = _find_project_root(Path.cwd())
    config_path = project_root / "agmd.yml"

    try:
        mappings = load_mappings(config_path)
        local_path_key = _normalize_local_path(args.path, project_root)
        path_mds = mappings.setdefault(local_path_key, [])
        github_slug = args.github_path.strip()
        existing_md = next(
            (md_entry for md_entry in path_mds if md_entry["name"] == github_slug), None
        )
        if existing_md is None:
            path_mds.append({"name": github_slug, "module": bool(args.module)})
        elif args.module:
            existing_md["module"] = True
        write_mappings(config_path, mappings)
        refreshed_paths = refresh_agents_files(
            project_root=project_root, mappings=mappings
        )
        downloaded_files = 0
        if args.module:
            target_dir = (project_root / local_path_key).resolve()
            downloaded_files = _download_github_module(
                github_path=github_slug,
                destination_root=target_dir,
            )
    except ValueError as exc:
        print(str(exc))
        return 1

    print(f"Updated {config_path} with md {github_slug!r} at path {local_path_key!r}")
    if args.module:
        print(
            f"Downloaded {downloaded_files} module file(s) to "
            f"{(project_root / local_path_key / '.agmd').resolve()}"
        )
    for refreshed in refreshed_paths:
        print(f"Refreshed {refreshed}")
    return 0
