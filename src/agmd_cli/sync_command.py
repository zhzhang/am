"""Implementation for the `agmd sync` command."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import module_helpers
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
        rebuilt_module_paths: list[tuple[Path, int]] = []
        project_root_resolved = project_root.resolve()
        for path_key, mds in mappings.items():
            module_github_paths = [md_entry["name"] for md_entry in mds if md_entry["module"]]
            target_dir = (project_root / path_key).resolve()
            try:
                target_dir.relative_to(project_root_resolved)
            except ValueError as exc:
                raise ValueError(
                    f"Configured path '{path_key}' must be within project root '{project_root}'."
                ) from exc

            modules_root = target_dir / ".agmd"
            had_modules_dir = modules_root.exists()
            if not module_github_paths and not had_modules_dir:
                continue

            downloaded_files = module_helpers.rebuild_modules_for_path(
                path_root=target_dir, github_paths=module_github_paths
            )
            rebuilt_module_paths.append((modules_root, downloaded_files))
    except ValueError as exc:
        print(str(exc))
        return 1

    if not refreshed_paths:
        print("No configured paths found in agmd.yml.")
        return 0

    for refreshed in refreshed_paths:
        print(f"Refreshed {refreshed}")
    for modules_root, downloaded_files in rebuilt_module_paths:
        print(f"Rebuilt {modules_root} ({downloaded_files} file(s))")
    return 0
