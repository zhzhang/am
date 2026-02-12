"""Shared helpers for AGENTS.md synchronization."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml

ROOT_AGENTS_PREAMBLE = (
    "This project's AGENTS.md files are managed by agmd, which may pull in "
    "AGENTS.md files from other sources.\n"
    "These external AGENTS.md files will be delimited by:\n"
    "# agmd start <module_name>.\n"
    "Any files referenced by these modules will be located relative to the "
    "AGENTS.md file at .agmd/<module_name>.\n"
)


class MdEntry(TypedDict):
    name: str
    module: bool


def _parse_name(name_value: object, config_path: Path) -> str:
    name = name_value
    if not isinstance(name, str) or not name.strip():
        raise ValueError(
            f"Invalid `name` value in {config_path}: {name_value!r}. "
            "Expected a non-empty string."
        )
    return name.strip()


def _parse_module(
    module_value: object, config_path: Path, path_value: str, name_value: str
) -> bool:
    if module_value is None:
        return False
    if isinstance(module_value, bool):
        return module_value
    raise ValueError(
        f"Invalid `module` value for path {path_value!r} and name {name_value!r} "
        f"in {config_path}: {module_value!r}. Expected a boolean."
    )


def load_mappings(config_path: Path) -> dict[str, list[MdEntry]]:
    if not config_path.exists():
        raise ValueError(f"Missing config file: {config_path}. Run `agmd init` first.")

    raw_data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if raw_data is None:
        return {}
    if not isinstance(raw_data, list):
        raise ValueError(
            f"Invalid config in {config_path}. Expected a top-level YAML list."
        )

    mappings: dict[str, list[MdEntry]] = {}

    for entry in raw_data:
        if not isinstance(entry, dict):
            raise ValueError(
                f"Invalid config entry in {config_path}: {entry!r}. "
                "Expected each list item to be a mapping."
            )

        path_value = entry.get("path")
        if not isinstance(path_value, str) or not path_value:
            raise ValueError(
                f"Invalid path value in {config_path}: {path_value!r}. "
                "Expected a non-empty string."
            )

        mds_value = entry.get("mds", [])
        if not isinstance(mds_value, list):
            raise ValueError(
                f"Invalid mds value for path {path_value!r} in {config_path}: "
                f"{mds_value!r}. Expected a list."
            )

        parsed_mds: list[MdEntry] = []
        for md_entry in mds_value:
            if not isinstance(md_entry, dict):
                raise ValueError(
                    f"Invalid md entry for path {path_value!r} in {config_path}: "
                    f"{md_entry!r}. Expected a mapping with `name` and `module`."
                )
            name = _parse_name(md_entry.get("name"), config_path)
            module = _parse_module(md_entry.get("module"), config_path, path_value, name)
            parsed_mds.append({"name": name, "module": module})

        mappings[path_value] = parsed_mds

    return mappings


def write_mappings(config_path: Path, mappings: dict[str, list[MdEntry]]) -> None:
    yaml_payload = [
        {"path": path, "mds": mds}
        for path, mds in mappings.items()
    ]
    rendered = yaml.safe_dump(
        yaml_payload,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=False,
    )
    config_path.write_text(rendered, encoding="utf-8")


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


def compose_agents_document(mds: list[MdEntry], local_agents_path: Path) -> str:
    sections: list[str] = []
    for md_entry in mds:
        github_path = md_entry["name"]
        remote_content = _fetch_remote_agents(github_path).strip()
        if remote_content:
            sections.append(f"# agmd start {github_path}.\n\n{remote_content}")

    if local_agents_path.exists():
        local_content = local_agents_path.read_text(encoding="utf-8").strip()
        if local_content:
            sections.append(f"# agmd local\n\n{local_content}")

    if not sections:
        return ""
    return "\n\n".join(sections) + "\n"


def refresh_agents_files(
    project_root: Path, mappings: dict[str, list[MdEntry]]
) -> list[Path]:
    refreshed_paths: list[Path] = []

    for path_key, mds in mappings.items():
        target_dir = (project_root / path_key).resolve()
        try:
            target_dir.relative_to(project_root.resolve())
        except ValueError as exc:
            raise ValueError(
                f"Configured path '{path_key}' must be within project root '{project_root}'."
            ) from exc

        target_dir.mkdir(parents=True, exist_ok=True)
        agents_content = compose_agents_document(
            mds=mds,
            local_agents_path=target_dir / "AGENTS.local.md",
        )
        if target_dir == project_root.resolve():
            if agents_content:
                agents_content = f"{ROOT_AGENTS_PREAMBLE}\n{agents_content}"
            else:
                agents_content = ROOT_AGENTS_PREAMBLE
        agents_path = target_dir / "AGENTS.md"
        agents_path.write_text(agents_content, encoding="utf-8")
        refreshed_paths.append(agents_path)

    return refreshed_paths
