"""Implementation for the `agmd add` command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .sync_helpers import load_mappings, refresh_agents_file


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


def _render_config_yaml(mappings: dict[str, str]) -> str:
    if not mappings:
        return "mappings: {}\n"

    lines = ["mappings:"]
    for path, slug in mappings.items():
        # JSON-quoted strings are valid YAML scalars and handle escaping safely.
        lines.append(f"  {json.dumps(path)}: {json.dumps(slug)}")
    return "\n".join(lines) + "\n"


def register_add_command(subparsers: argparse._SubParsersAction) -> None:
    add_parser = subparsers.add_parser(
        "add",
        help="Add a GitHub path mapping and refresh AGENTS.md.",
    )
    add_parser.add_argument(
        "github_path",
        help="GitHub slug (owner/repo[/path]).",
    )
    add_parser.add_argument(
        "--path",
        default=".",
        metavar="PATH",
        help="Local path key to map in agmd.yml (defaults to project root).",
    )
    add_parser.set_defaults(handler=run_add_command)


def run_add_command(args: argparse.Namespace) -> int:
    project_root = _find_project_root(Path.cwd())
    config_path = project_root / "agmd.yml"

    try:
        mappings = load_mappings(config_path)
        local_path_key = _normalize_local_path(args.path, project_root)
        mappings[local_path_key] = args.github_path.strip()
        config_path.write_text(_render_config_yaml(mappings), encoding="utf-8")
        refresh_agents_file(project_root=project_root, mappings=mappings)
    except ValueError as exc:
        print(str(exc))
        return 1

    print(
        f"Updated {config_path} with mapping {local_path_key!r} -> {args.github_path!r}"
    )
    print(f"Refreshed {(project_root / 'AGENTS.md')}")
    return 0
