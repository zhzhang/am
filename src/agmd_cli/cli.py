"""Command-line interface for agmd."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agmd_cli import __version__


def _find_project_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    return start


def _parse_mapping_entries(entries: list[str], project_root: Path) -> dict[str, str]:
    mappings: dict[str, str] = {}

    for entry in entries:
        if "=" not in entry:
            raise ValueError(
                f"Invalid mapping '{entry}'. Expected format: <path>=<github-url-slug>."
            )
        raw_path, slug = entry.split("=", 1)
        path = raw_path.strip()
        slug = slug.strip()

        if not path:
            raise ValueError(f"Invalid mapping '{entry}'. Path cannot be empty.")
        if not slug:
            raise ValueError(
                f"Invalid mapping '{entry}'. GitHub URL slug cannot be empty."
            )

        normalized_path = Path(path)
        if not normalized_path.is_absolute():
            normalized_path = (project_root / normalized_path).resolve()

        try:
            relative_path = normalized_path.relative_to(project_root.resolve())
        except ValueError as exc:
            raise ValueError(
                f"Path '{path}' must be within the project root '{project_root}'."
            ) from exc

        key = "." if str(relative_path) == "." else relative_path.as_posix()
        mappings[key] = slug

    return mappings


def _render_config_yaml(mappings: dict[str, str]) -> str:
    if not mappings:
        return "mappings: {}\n"

    lines = ["mappings:"]
    for path, slug in mappings.items():
        # JSON-quoted strings are valid YAML scalars and handle escaping safely.
        lines.append(f"  {json.dumps(path)}: {json.dumps(slug)}")
    return "\n".join(lines) + "\n"


def _ensure_gitignore_rule(project_root: Path, rule: str) -> None:
    gitignore_path = project_root / ".gitignore"

    existing_lines: list[str] = []
    if gitignore_path.exists():
        existing_lines = gitignore_path.read_text(encoding="utf-8").splitlines()

    if rule in existing_lines:
        return

    existing_lines.append(rule)
    gitignore_path.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")


def _move_agents_files(project_root: Path) -> int:
    moved_count = 0

    for agents_path in project_root.rglob("AGENTS.md"):
        if ".git" in agents_path.parts or not agents_path.is_file():
            continue
        local_path = agents_path.with_name("AGENTS.local.md")
        agents_path.replace(local_path)
        moved_count += 1

    return moved_count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agmd",
        description="A scaffolded Python CLI tool.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser(
        "init",
        help="Create agmd.yml in the project root.",
    )
    init_parser.add_argument(
        "-m",
        "--map",
        action="append",
        default=[],
        metavar="PATH=GITHUB_URL_SLUG",
        help="Add a path to GitHub URL slug mapping. Repeat for multiple mappings.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init":
        project_root = _find_project_root(Path.cwd())
        config_path = project_root / "agmd.yml"
        if config_path.exists():
            print(f"Skipped creating existing file: {config_path}")
        else:
            try:
                mappings = _parse_mapping_entries(args.map, project_root)
            except ValueError as exc:
                print(str(exc))
                return 1

            config = {
                "mappings": mappings,
            }
            config_path.write_text(
                _render_config_yaml(config["mappings"]),
                encoding="utf-8",
            )
            print(f"Created {config_path}")
        _ensure_gitignore_rule(project_root, "AGENTS.md")
        moved_count = _move_agents_files(project_root)
        print(f"Updated {(project_root / '.gitignore')} to ignore AGENTS.md")
        print(f"Renamed {moved_count} AGENTS.md file(s) to AGENTS.local.md")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
