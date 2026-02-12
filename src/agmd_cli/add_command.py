"""Implementation for the `agmd add` command."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import module_helpers
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
            "Target path is not just a single AGENTS.md but a directory of files. Download every file from the GitHub path into "
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
            downloaded_files = module_helpers.download_github_module(
                github_path=github_slug,
                destination_root=target_dir,
            )
    except ValueError as exc:
        print(str(exc))
        return 1

    print(f"Added {config_path} at path {local_path_key!r}")
    if args.module:
        print(
            f"Downloaded {downloaded_files} module file(s) to "
            f"{(project_root / local_path_key / '.agmd').resolve()}"
        )
    for refreshed in refreshed_paths:
        print(f"Refreshed {refreshed}")
    return 0
