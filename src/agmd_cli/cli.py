"""Command-line interface for agmd."""

from __future__ import annotations

import argparse

from . import __version__
from .add_command import register_add_command
from .init_command import register_init_command
from .sync_command import register_sync_command


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

    register_add_command(subparsers)
    register_init_command(subparsers)
    register_sync_command(subparsers)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    handler = getattr(args, "handler", None)
    if callable(handler):
        return handler(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
