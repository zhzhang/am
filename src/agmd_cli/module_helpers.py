"""Helpers for downloading and rebuilding module files under `.agmd`."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def _parse_github_path(github_path: str) -> tuple[str, str, list[str]]:
    cleaned = github_path.strip().strip("/")
    parts = [part for part in cleaned.split("/") if part]
    if len(parts) < 2:
        raise ValueError(
            f"Invalid GitHub path '{github_path}'. Expected at least <owner>/<repo>."
        )
    return parts[0], parts[1], parts[2:]


def _github_contents_api_url(owner: str, repo: str, path_in_repo: str) -> str:
    if path_in_repo:
        encoded_path = quote(path_in_repo, safe="/")
        return f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded_path}?ref=main"
    return f"https://api.github.com/repos/{owner}/{repo}/contents?ref=main"


def _module_slug_directory_name(github_path: str) -> str:
    cleaned = github_path.strip().strip("/")
    if not cleaned:
        raise ValueError("GitHub path cannot be empty.")
    return re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned)


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


def download_github_module(github_path: str, destination_root: Path) -> int:
    """Download all files at `github_path` into `<destination_root>/.agmd/...`."""
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


def rebuild_modules_for_path(path_root: Path, github_paths: list[str]) -> int:
    """
    Rebuild `<path_root>/.agmd` from the provided module-enabled GitHub paths.

    Existing `.agmd` content is removed first to keep generated modules in sync.
    """
    modules_root = path_root / ".agmd"
    if modules_root.is_dir():
        shutil.rmtree(modules_root)
    elif modules_root.exists():
        modules_root.unlink()

    downloaded_files = 0
    for github_path in github_paths:
        downloaded_files += download_github_module(github_path, path_root)
    return downloaded_files
