"""Implementation for the `agmd sync` command."""

from __future__ import annotations

import argparse
from pathlib import Path

from .sync_helpers import load_mappings, refresh_agents_files


def _find_project_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    return start


def register_sync_command(subparsers: argparse._SubParsersAction) -> None:
    sync_parser = subparsers.add_parser(
        "sync",
        help="Refresh AGENTS.md files from current agmd.yml mappings.",
    )
    sync_parser.set_defaults(handler=run_sync_command)


def run_sync_command(args: argparse.Namespace) -> int:
    _ = args
    project_root = _find_project_root(Path.cwd())
    config_path = project_root / "agmd.yml"

    try:
        mappings = load_mappings(config_path)
        refreshed_paths = refresh_agents_files(project_root=project_root, mappings=mappings)
    except ValueError as exc:
        print(str(exc))
        return 1

    if not refreshed_paths:
        print("No configured paths found in agmd.yml.")
        return 0

    for refreshed in refreshed_paths:
        print(f"Refreshed {refreshed}")
    return 0
