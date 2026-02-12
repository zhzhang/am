"""Shared helpers for AGENTS.md synchronization."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def load_mappings(config_path: Path) -> dict[str, str]:
    if not config_path.exists():
        raise ValueError(f"Missing config file: {config_path}. Run `agmd init` first.")

    lines = config_path.read_text(encoding="utf-8").splitlines()
    non_empty_lines = [line for line in lines if line.strip()]
    if not non_empty_lines:
        return {}

    if len(non_empty_lines) == 1 and non_empty_lines[0].strip() == "mappings: {}":
        return {}

    if non_empty_lines[0].strip() != "mappings:":
        raise ValueError(
            f"Invalid config in {config_path}. Expected top-level `mappings:` key."
        )

    mappings: dict[str, str] = {}
    for line in non_empty_lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue

        if ":" not in stripped:
            raise ValueError(
                f"Invalid mapping line in {config_path}: {line!r}. "
                'Expected format: "<path>": "<github-path>"'
            )

        key_literal, value_literal = stripped.split(":", 1)
        key = json.loads(key_literal.strip())
        value = json.loads(value_literal.strip())
        mappings[key] = value

    return mappings


def _github_agents_url(github_path: str) -> str:
    cleaned = github_path.strip().rstrip("/")
    slug_parts = [part for part in cleaned.split("/") if part]
    if len(slug_parts) < 2:
        raise ValueError(
            f"Invalid GitHub path '{github_path}'. Expected at least <owner>/<repo>."
        )

    owner, repo = slug_parts[0], slug_parts[1]
    relative_path = slug_parts[2:]
    agents_path = (
        "/".join([*relative_path, "AGENTS.md"]) if relative_path else "AGENTS.md"
    )
    return f"https://raw.githubusercontent.com/{owner}/{repo}/refs/heads/main/{agents_path}"


def _fetch_remote_agents(github_path: str) -> str:
    url = _github_agents_url(github_path)
    request = Request(url, headers={"User-Agent": "agmd-cli/0.1"})
    try:
        with urlopen(request, timeout=20) as response:  # nosec B310
            return response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ValueError(
            f"Failed to fetch AGENTS.md for '{github_path}' at {url}. Error: {exc}"
        ) from exc


def compose_agents_document(mappings: dict[str, str], local_agents_path: Path) -> str:
    sections: list[str] = []
    for github_path in mappings.values():
        remote_content = _fetch_remote_agents(github_path).strip()
        if remote_content:
            sections.append(remote_content)

    if local_agents_path.exists():
        local_content = local_agents_path.read_text(encoding="utf-8").strip()
        if local_content:
            sections.append(local_content)

    if not sections:
        return ""
    return "\n\n".join(sections) + "\n"


def refresh_agents_file(project_root: Path, mappings: dict[str, str]) -> Path:
    agents_content = compose_agents_document(
        mappings=mappings,
        local_agents_path=project_root / "AGENTS.local.md",
    )
    agents_path = project_root / "AGENTS.md"
    agents_path.write_text(agents_content, encoding="utf-8")
    return agents_path
