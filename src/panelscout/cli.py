"""Command line entry point for the PanelScout MVP skeleton."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from panelscout import __version__
from panelscout.config import ConfigError, load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="panelscout",
        description="PanelScout local metadata CLI.",
    )
    parser.add_argument(
        "--config",
        help="Path to a PanelScout TOML config file.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show the PanelScout version and exit.",
    )

    subparsers = parser.add_subparsers(dest="command")

    config_parser = subparsers.add_parser("config", help="Inspect local config.")
    config_parser.set_defaults(handler=_handle_config_show, json=False)
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    config_show = config_subparsers.add_parser("show", help="Show effective config.")
    config_show.add_argument(
        "--json",
        action="store_true",
        help="Print config as JSON.",
    )
    config_show.set_defaults(handler=_handle_config_show)

    search_parser = subparsers.add_parser("search", help="Search comics by metadata.")
    search_parser.add_argument("query", nargs="?", help="Search keyword.")
    search_parser.add_argument(
        "--source",
        default=None,
        help="Source adapter to use. Defaults to the configured source.",
    )
    search_parser.set_defaults(handler=_handle_placeholder)

    sync_parser = subparsers.add_parser("sync", help="Refresh saved metadata.")
    sync_parser.set_defaults(handler=_handle_placeholder)

    watch_parser = subparsers.add_parser("watch", help="Check watched comics.")
    watch_parser.set_defaults(handler=_handle_placeholder)

    export_parser = subparsers.add_parser("export", help="Export collected metadata.")
    export_parser.add_argument(
        "--format",
        choices=("json", "csv", "markdown"),
        default="json",
        help="Export format.",
    )
    export_parser.set_defaults(handler=_handle_placeholder)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"PanelScout {__version__}")
        return 0

    if not args.command:
        parser.print_help()
        return 0

    try:
        config = load_config(args.config)
        handler = getattr(args, "handler", None)
        if handler is None:
            parser.print_help()
            return 0
        return handler(args, config)
    except ConfigError as error:
        print(f"panelscout: {error}", file=sys.stderr)
        return 1


def _handle_config_show(args: argparse.Namespace, config) -> int:
    values = config.as_display_dict()
    if args.json:
        print(json.dumps(values, indent=2, sort_keys=True))
    else:
        for key in sorted(values):
            print(f"{key}={values[key]}")
    return 0


def _handle_placeholder(args: argparse.Namespace, config) -> int:
    command = args.command
    source = getattr(args, "source", None) or config.source
    print(
        f"'{command}' is reserved for the metadata MVP and is not implemented "
        f"in this Unit 1 skeleton. Source: {source}. No network request was made."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
