"""Command line entry point for the PanelScout MVP skeleton."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from panelscout import __version__
from panelscout.adapters.zaimanhua import SOURCE_NAME, build_robots_url
from panelscout.config import ConfigError, load_config
from panelscout.crawler import (
    FetchError,
    HtmlFetcher,
    RobotsDisallowedError,
    RobotsLoadError,
    check_watchlist_public_updates,
    load_robots_policy,
    normalize_detail_reference,
    search_public_comics,
    sync_public_detail,
)
from panelscout.exporters import (
    export_comics_csv,
    export_comics_json,
    export_comics_markdown,
    export_watch_check_markdown,
)
from panelscout.storage import ComicRepository, StorageError, connect_database
from panelscout.ui import build_local_ui_state, write_local_ui_shell


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
    search_parser.add_argument(
        "--save",
        action="store_true",
        help="Save search results to the configured SQLite database.",
    )
    search_parser.set_defaults(handler=_handle_search)

    sync_parser = subparsers.add_parser("sync", help="Refresh public comic details.")
    sync_parser.add_argument("reference", nargs="?", help="Source comic id or details URL.")
    sync_parser.add_argument(
        "--source",
        default=None,
        help="Source adapter to use. Defaults to the configured source.",
    )
    sync_parser.add_argument(
        "--save",
        action="store_true",
        help="Save synced details and chapters to the configured SQLite database.",
    )
    sync_parser.set_defaults(handler=_handle_sync)

    watch_parser = subparsers.add_parser("watch", help="Manage watched comics.")
    watch_subparsers = watch_parser.add_subparsers(dest="watch_command")
    watch_list = watch_subparsers.add_parser("list", help="List watched comics.")
    watch_list.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of watchlist entries to show.",
    )
    watch_list.set_defaults(handler=_handle_watch_list)
    watch_add = watch_subparsers.add_parser(
        "add",
        help="Add an existing local catalog comic to the watchlist.",
    )
    watch_add.add_argument("source_comic_id", nargs="?", help="Source comic id to watch.")
    watch_add.add_argument(
        "--source",
        default=None,
        help="Source adapter to use. Defaults to the configured source.",
    )
    watch_add.add_argument("--notes", help="Optional local notes for this watch entry.")
    watch_add.set_defaults(handler=_handle_watch_add)
    watch_remove = watch_subparsers.add_parser(
        "remove",
        help="Remove a comic from the watchlist.",
    )
    watch_remove.add_argument("source_comic_id", nargs="?", help="Source comic id to remove.")
    watch_remove.add_argument(
        "--source",
        default=None,
        help="Source adapter to use. Defaults to the configured source.",
    )
    watch_remove.set_defaults(handler=_handle_watch_remove)
    watch_check = watch_subparsers.add_parser(
        "check",
        help="Check watched comics for public metadata updates.",
    )
    watch_check.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of watchlist entries to check.",
    )
    watch_check.add_argument(
        "--source",
        default=None,
        help="Source adapter to use. Defaults to the configured source.",
    )
    watch_check.add_argument(
        "--report",
        help="Optional Markdown file path for the watch check report.",
    )
    watch_check.set_defaults(handler=_handle_watch_check)
    watch_schedule = watch_subparsers.add_parser(
        "schedule",
        help="Manage local suggested watch check schedules.",
    )
    watch_schedule_subparsers = watch_schedule.add_subparsers(
        dest="watch_schedule_command"
    )
    watch_schedule_show = watch_schedule_subparsers.add_parser(
        "show",
        help="Show the local watch check schedule.",
    )
    watch_schedule_show.add_argument(
        "--source",
        default=None,
        help="Source adapter to use. Defaults to the configured source.",
    )
    watch_schedule_show.set_defaults(handler=_handle_watch_schedule_show)
    watch_schedule_set = watch_schedule_subparsers.add_parser(
        "set",
        help="Set a local suggested watch check schedule.",
    )
    watch_schedule_set.add_argument(
        "--interval-minutes",
        type=int,
        required=True,
        help="Suggested minutes between manual watch checks.",
    )
    watch_schedule_set.add_argument(
        "--source",
        default=None,
        help="Source adapter to use. Defaults to the configured source.",
    )
    watch_schedule_set.set_defaults(handler=_handle_watch_schedule_set)
    watch_schedule_clear = watch_schedule_subparsers.add_parser(
        "clear",
        help="Clear the local watch check schedule.",
    )
    watch_schedule_clear.add_argument(
        "--source",
        default=None,
        help="Source adapter to use. Defaults to the configured source.",
    )
    watch_schedule_clear.set_defaults(handler=_handle_watch_schedule_clear)
    watch_schedule_due = watch_schedule_subparsers.add_parser(
        "due",
        help="Show whether a local watch check schedule is due.",
    )
    watch_schedule_due.add_argument(
        "--source",
        default=None,
        help="Source adapter to use. Defaults to the configured source.",
    )
    watch_schedule_due.set_defaults(handler=_handle_watch_schedule_due)
    watch_schedule.set_defaults(
        handler=_handle_watch_schedule_show,
        watch_schedule_command="show",
    )
    watch_parser.set_defaults(handler=_handle_watch_list, watch_command="list", limit=100)

    ui_parser = subparsers.add_parser("ui", help="生成本地 UI 文件。")
    ui_subparsers = ui_parser.add_subparsers(dest="ui_command")
    ui_build = ui_subparsers.add_parser(
        "build",
        help="生成 MVP4 本地静态 UI。",
    )
    ui_build.add_argument(
        "--output",
        required=True,
        help="输出 HTML 文件路径。",
    )
    ui_build.set_defaults(handler=_handle_ui_build)
    ui_parser.set_defaults(handler=_handle_ui_help)

    export_parser = subparsers.add_parser("export", help="Export collected metadata.")
    export_parser.add_argument(
        "--format",
        choices=("json", "csv", "markdown"),
        default="json",
        help="Export format.",
    )
    export_parser.add_argument(
        "--output",
        help="Optional output file. Defaults to stdout.",
    )
    export_parser.set_defaults(handler=_handle_export)

    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    search_fetcher_factory=None,
    sync_fetcher_factory=None,
) -> int:
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
        if args.command == "search" and search_fetcher_factory is not None:
            args.search_fetcher_factory = search_fetcher_factory
        if args.command == "sync" and sync_fetcher_factory is not None:
            args.sync_fetcher_factory = sync_fetcher_factory
        if (
            args.command == "watch"
            and getattr(args, "watch_command", None) == "check"
            and sync_fetcher_factory is not None
        ):
            args.sync_fetcher_factory = sync_fetcher_factory
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


def _handle_search(args: argparse.Namespace, config) -> int:
    query = (args.query or "").strip()
    if not query:
        print("panelscout: search query cannot be blank", file=sys.stderr)
        return 1

    source = args.source or config.source
    if source != SOURCE_NAME:
        print(f"panelscout: unsupported search source '{source}'", file=sys.stderr)
        return 1

    factory = getattr(args, "search_fetcher_factory", None) or _create_search_fetcher
    try:
        fetcher = factory(config)
        if args.save:
            with connect_database(config.database_path) as connection:
                result = search_public_comics(
                    query,
                    fetcher,
                    repository=ComicRepository(connection),
                )
        else:
            result = search_public_comics(query, fetcher)
    except RobotsLoadError as error:
        print(f"panelscout: robots policy unavailable; search aborted: {error}", file=sys.stderr)
        return 1
    except RobotsDisallowedError as error:
        print(f"panelscout: robots policy disallowed search: {error}", file=sys.stderr)
        return 1
    except FetchError as error:
        print(f"panelscout: search fetch failed: {error}", file=sys.stderr)
        return 1

    print(_format_search_result(result, saved=args.save))
    return 0


def _handle_sync(args: argparse.Namespace, config) -> int:
    reference = (args.reference or "").strip()
    if not reference:
        print("panelscout: sync reference cannot be blank", file=sys.stderr)
        return 1

    source = args.source or config.source
    if source != SOURCE_NAME:
        print(f"panelscout: unsupported sync source '{source}'", file=sys.stderr)
        return 1

    try:
        normalize_detail_reference(reference)
    except ValueError as error:
        print(f"panelscout: sync reference invalid: {error}", file=sys.stderr)
        return 1

    factory = getattr(args, "sync_fetcher_factory", None) or _create_sync_fetcher
    try:
        fetcher = factory(config)
        database_path = config.database_path if args.save else ":memory:"
        with connect_database(database_path) as connection:
            result = sync_public_detail(
                reference,
                fetcher,
                ComicRepository(connection),
            )
    except RobotsLoadError as error:
        print(f"panelscout: robots policy unavailable; sync aborted: {error}", file=sys.stderr)
        return 1
    except RobotsDisallowedError as error:
        print(f"panelscout: robots policy disallowed sync: {error}", file=sys.stderr)
        return 1
    except FetchError as error:
        print(f"panelscout: sync fetch failed: {error}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"panelscout: sync failed: {error}", file=sys.stderr)
        return 1

    print(_format_sync_result(result, saved=args.save))
    return 0


def _create_search_fetcher(config):
    robots_policy = load_robots_policy(
        build_robots_url(),
        user_agent=config.user_agent,
    )
    return HtmlFetcher(config=config, robots_policy=robots_policy)


def _create_sync_fetcher(config):
    robots_policy = load_robots_policy(
        build_robots_url(),
        user_agent=config.user_agent,
    )
    return HtmlFetcher(config=config, robots_policy=robots_policy)


def _format_search_result(result, *, saved: bool) -> str:
    lines = [
        f"Search results for: {result.query}",
        f"Source URL: {result.url}",
        f"Found: {len(result.comics)}",
    ]
    if saved:
        lines.append(f"Saved: {result.persisted_count}")
    lines.append("")

    if not result.comics:
        lines.append("No results found.")
        return "\n".join(lines)

    for index, comic in enumerate(result.comics, start=1):
        author = f" by {comic.author}" if comic.author else ""
        latest = f" | latest: {comic.latest_chapter_title}" if comic.latest_chapter_title else ""
        status = f" | status: {comic.status}" if comic.status else ""
        lines.append(f"{index}. {comic.title}{author}{latest}{status}")
        lines.append(f"   id: {comic.source_comic_id}")
        if comic.detail_url:
            lines.append(f"   url: {comic.detail_url}")
    return "\n".join(lines)


def _format_sync_result(result, *, saved: bool) -> str:
    comic = result.comic
    lines = [
        f"Synced detail: {comic.title}",
        f"Source URL: {result.detail_url}",
        f"id: {comic.source_comic_id}",
    ]
    if comic.author:
        lines.append(f"Author: {comic.author}")
    if comic.status:
        lines.append(f"Status: {comic.status}")
    if comic.latest_chapter_title:
        lines.append(f"Latest: {comic.latest_chapter_title}")
    lines.extend(
        [
            f"Chapters: {result.chapter_count}",
            f"New chapters: {result.new_chapter_count}",
            f"Existing chapters: {result.existing_chapter_count}",
            f"Saved: {'yes' if saved else 'no (dry run)'}",
            "",
        ]
    )

    if result.metadata_changes:
        lines.append("Metadata changes:")
        for change in result.metadata_changes:
            lines.append(
                f"- {_display_metadata_field(change.field)}: "
                f"{_display_optional(change.previous)} -> {_display_optional(change.current)}"
            )
        lines.append("")

    if result.new_chapters:
        lines.append("New chapter details:")
        for index, chapter in enumerate(result.new_chapters, start=1):
            lines.append(f"{index}. {chapter.title}")
            lines.append(f"   url: {chapter.chapter_url}")
        lines.append("")

    if not result.chapters:
        lines.append("No visible chapters found.")
        return "\n".join(lines)

    lines.append("Visible chapters:")
    for index, chapter in enumerate(result.chapters, start=1):
        lines.append(f"{index}. {chapter.title}")
        lines.append(f"   url: {chapter.chapter_url}")
    return "\n".join(lines)


def _display_metadata_field(field: str) -> str:
    labels = {
        "title": "Title",
        "author": "Author",
        "status": "Status",
        "latest_chapter_title": "Latest chapter",
    }
    return labels.get(field, field)


def _display_optional(value: str | None) -> str:
    return value if value else "(none)"


def _handle_watch_list(args: argparse.Namespace, config) -> int:
    with connect_database(config.database_path) as connection:
        entries = ComicRepository(connection).list_watchlist_entries(limit=args.limit)

    print(_format_watchlist_entries(entries))
    return 0


def _handle_watch_add(args: argparse.Namespace, config) -> int:
    source_comic_id = (args.source_comic_id or "").strip()
    if not source_comic_id:
        print("panelscout: watch add source comic id cannot be blank", file=sys.stderr)
        return 1

    source = args.source or config.source
    if source != SOURCE_NAME:
        print(f"panelscout: unsupported watch source '{source}'", file=sys.stderr)
        return 1

    try:
        with connect_database(config.database_path) as connection:
            entry = ComicRepository(connection).add_watchlist_entry(
                source,
                source_comic_id,
                notes=args.notes,
            )
    except StorageError as error:
        print(f"panelscout: watch add failed: {error}", file=sys.stderr)
        return 1

    print(f"Watching: {entry.comic.title}")
    print(f"id: {entry.comic.source_comic_id}")
    if entry.notes:
        print(f"Notes: {entry.notes}")
    return 0


def _handle_watch_remove(args: argparse.Namespace, config) -> int:
    source_comic_id = (args.source_comic_id or "").strip()
    if not source_comic_id:
        print("panelscout: watch remove source comic id cannot be blank", file=sys.stderr)
        return 1

    source = args.source or config.source
    if source != SOURCE_NAME:
        print(f"panelscout: unsupported watch source '{source}'", file=sys.stderr)
        return 1

    with connect_database(config.database_path) as connection:
        removed = ComicRepository(connection).remove_watchlist_entry(source, source_comic_id)

    if not removed:
        print(f"panelscout: watch entry not found: {source_comic_id}", file=sys.stderr)
        return 1

    print(f"Removed watch entry: {source_comic_id}")
    return 0


def _handle_watch_check(args: argparse.Namespace, config) -> int:
    source = args.source or config.source
    if source != SOURCE_NAME:
        print(f"panelscout: unsupported watch source '{source}'", file=sys.stderr)
        return 1

    factory = getattr(args, "sync_fetcher_factory", None) or _create_sync_fetcher
    try:
        fetcher = factory(config)
        with connect_database(config.database_path) as connection:
            result = check_watchlist_public_updates(
                fetcher,
                ComicRepository(connection),
                limit=args.limit,
            )
    except RobotsLoadError as error:
        print(
            f"panelscout: robots policy unavailable; watch check aborted: {error}",
            file=sys.stderr,
        )
        return 1
    except RobotsDisallowedError as error:
        print(f"panelscout: robots policy disallowed watch check: {error}", file=sys.stderr)
        return 1
    except FetchError as error:
        print(f"panelscout: watch check fetcher setup failed: {error}", file=sys.stderr)
        return 1

    if args.report:
        report_path = Path(args.report).expanduser()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(export_watch_check_markdown(result), encoding="utf-8")

    print(_format_watch_check_result(result))
    if args.report:
        print(f"Report: {report_path}")
    return 0


def _handle_watch_schedule_show(args: argparse.Namespace, config) -> int:
    source = args.source or config.source
    if source != SOURCE_NAME:
        print(f"panelscout: unsupported watch schedule source '{source}'", file=sys.stderr)
        return 1

    with connect_database(config.database_path) as connection:
        schedule = ComicRepository(connection).get_watch_check_schedule(source)

    print(_format_watch_schedule(schedule, source=source))
    return 0


def _handle_watch_schedule_set(args: argparse.Namespace, config) -> int:
    source = args.source or config.source
    if source != SOURCE_NAME:
        print(f"panelscout: unsupported watch schedule source '{source}'", file=sys.stderr)
        return 1

    try:
        with connect_database(config.database_path) as connection:
            schedule = ComicRepository(connection).set_watch_check_schedule(
                source,
                interval_minutes=args.interval_minutes,
            )
    except StorageError as error:
        print(f"panelscout: watch schedule set failed: {error}", file=sys.stderr)
        return 1

    print(f"Watch schedule set: {schedule.source}")
    print(f"Interval minutes: {schedule.interval_minutes}")
    print(f"Next run: {schedule.next_run_at}")
    return 0


def _handle_watch_schedule_clear(args: argparse.Namespace, config) -> int:
    source = args.source or config.source
    if source != SOURCE_NAME:
        print(f"panelscout: unsupported watch schedule source '{source}'", file=sys.stderr)
        return 1

    with connect_database(config.database_path) as connection:
        removed = ComicRepository(connection).clear_watch_check_schedule(source)

    if removed:
        print(f"Watch schedule cleared: {source}")
    else:
        print(f"No watch schedule configured for {source}.")
    return 0


def _handle_watch_schedule_due(args: argparse.Namespace, config) -> int:
    source = args.source or config.source
    if source != SOURCE_NAME:
        print(f"panelscout: unsupported watch schedule source '{source}'", file=sys.stderr)
        return 1

    with connect_database(config.database_path) as connection:
        schedules = [
            schedule
            for schedule in ComicRepository(connection).list_due_watch_check_schedules()
            if schedule.source == source
        ]

    if not schedules:
        print(f"No watch check schedule due for {source}.")
        return 0

    print(f"Due watch check schedules: {len(schedules)}")
    for schedule in schedules:
        print(f"- {schedule.source}: next run {schedule.next_run_at}")
    return 0


def _handle_ui_help(args: argparse.Namespace, config) -> int:
    print("panelscout ui build --output PATH")
    print("生成本地静态 UI；不会启动服务，也不会发起网络请求。")
    return 0


def _handle_ui_build(args: argparse.Namespace, config) -> int:
    output = (args.output or "").strip()
    if not output:
        print("panelscout：ui build 输出路径不能为空", file=sys.stderr)
        return 1

    state = build_local_ui_state(config)
    output_path = write_local_ui_shell(output, state=state)
    print(f"UI 文件已写入：{output_path}")
    print(f"UI 数据：{state.data_status}")
    print("请在本地打开 HTML 文件。未启动服务、网络、登录或下载任务。")
    return 0


def _format_watchlist_entries(entries) -> str:
    lines = [f"Watchlist entries: {len(entries)}", ""]
    if not entries:
        lines.append("No watched comics.")
        return "\n".join(lines)

    for index, entry in enumerate(entries, start=1):
        comic = entry.comic
        author = f" by {comic.author}" if comic.author else ""
        latest = f" | latest: {comic.latest_chapter_title}" if comic.latest_chapter_title else ""
        status = f" | status: {comic.status}" if comic.status else ""
        lines.append(f"{index}. {comic.title}{author}{latest}{status}")
        lines.append(f"   id: {comic.source_comic_id}")
        if comic.detail_url:
            lines.append(f"   url: {comic.detail_url}")
        if entry.notes:
            lines.append(f"   notes: {entry.notes}")
    return "\n".join(lines)


def _format_watch_schedule(schedule, *, source: str) -> str:
    if schedule is None:
        return f"No watch schedule configured for {source}."

    lines = [
        f"Watch schedule: {schedule.source}",
        f"Enabled: {'yes' if schedule.enabled else 'no'}",
        f"Interval minutes: {schedule.interval_minutes}",
        f"Next run: {schedule.next_run_at}",
    ]
    if schedule.last_run_at:
        lines.append(f"Last run: {schedule.last_run_at}")
    return "\n".join(lines)


def _format_watch_check_result(result) -> str:
    lines = [
        "Watch check complete",
        f"Checked: {result.checked_count}",
        f"Succeeded: {result.success_count}",
        f"Failed: {result.failure_count}",
        f"New chapters: {result.new_chapter_count}",
        f"Metadata changes: {result.metadata_change_count}",
        "",
    ]

    if not result.items:
        lines.append("No watched comics to check.")
        return "\n".join(lines)

    for index, item in enumerate(result.items, start=1):
        comic = item.entry.comic
        lines.append(f"{index}. {comic.title}")
        lines.append(f"   id: {comic.source_comic_id}")
        if item.error:
            lines.append(f"   status: failed")
            lines.append(f"   error: {item.error}")
            continue

        assert item.sync_result is not None
        sync_result = item.sync_result
        lines.append("   status: checked")
        lines.append(f"   new chapters: {sync_result.new_chapter_count}")
        lines.append(f"   metadata changes: {len(sync_result.metadata_changes)}")
        if sync_result.new_chapters:
            lines.append("   new chapter details:")
            for chapter in sync_result.new_chapters:
                lines.append(f"   - {chapter.title}")
        if sync_result.metadata_changes:
            lines.append("   metadata change details:")
            for change in sync_result.metadata_changes:
                lines.append(
                    f"   - {_display_metadata_field(change.field)}: "
                    f"{_display_optional(change.previous)} -> "
                    f"{_display_optional(change.current)}"
                )
    return "\n".join(lines)


def _handle_export(args: argparse.Namespace, config) -> int:
    comics = _load_export_comics(config.database_path)

    rendered = _render_export(comics, args.format)

    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="" if rendered.endswith("\n") else "\n")

    return 0


def _load_export_comics(database_path: Path) -> list:
    if str(database_path) != ":memory:" and not Path(database_path).expanduser().exists():
        return []

    with connect_database(database_path) as connection:
        return ComicRepository(connection).list_comics(limit=500)


def _render_export(comics, export_format: str) -> str:
    if export_format == "json":
        return export_comics_json(comics)
    if export_format == "csv":
        return export_comics_csv(comics)
    if export_format == "markdown":
        return export_comics_markdown(comics)
    raise ValueError(f"Unsupported export format: {export_format}")


if __name__ == "__main__":
    raise SystemExit(main())
