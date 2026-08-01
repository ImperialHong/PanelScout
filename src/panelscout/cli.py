"""Command line entry point for the PanelScout MVP skeleton."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Sequence

from panelscout import __version__
from panelscout.adapters.zaimanhua import (
    CHAPTER_DETAIL_API_ROBOTS_ALLOW_PATH,
    DETAIL_API_ROBOTS_ALLOW_PATH,
    SEARCH_API_ROBOTS_ALLOW_PATH,
    SOURCE_NAME,
    build_robots_url,
)
from panelscout.auth import (
    CHAPTER_IMAGE_RENDER_SELECTOR,
    AuthenticatedBrowserHtmlFetcher,
    AuthSessionError,
    BrowserLoginResult,
    auth_start_url,
    default_auth_session_path,
    run_manual_browser_login,
)
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
from panelscout.downloader import (
    ImageFetcher,
    plan_public_chapter_download,
    save_public_chapter_download,
)
from panelscout.exporters import (
    export_comics_csv,
    export_comics_json,
    export_comics_markdown,
    export_watch_check_markdown,
)
from panelscout.storage import AuthSession, ComicRepository, StorageError, connect_database
from panelscout.ui import (
    build_local_ui_state,
    serve_local_ui,
    write_local_ui_shell,
)


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
    search_parser.add_argument(
        "--auth",
        nargs="?",
        const=True,
        default=False,
        help="Use a saved local authenticated browser session to render search results.",
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
    sync_parser.add_argument(
        "--auth",
        nargs="?",
        const=True,
        default=False,
        help="Use a saved local authenticated browser session. Optionally pass source.",
    )
    sync_parser.set_defaults(handler=_handle_sync)

    auth_parser = subparsers.add_parser(
        "auth",
        help="Manage local authenticated browser sessions.",
    )
    auth_subparsers = auth_parser.add_subparsers(dest="auth_command")
    auth_login = auth_subparsers.add_parser(
        "login",
        help="Open a local browser for user-driven login and save storage state.",
    )
    auth_login.add_argument(
        "source",
        nargs="?",
        help="Source adapter to log in to. Defaults to the configured source.",
    )
    auth_login.add_argument(
        "--session-path",
        help="Storage-state JSON path. Defaults to the configured session_dir.",
    )
    auth_login.add_argument(
        "--start-url",
        help="Optional source URL to open for manual login.",
    )
    auth_login.add_argument(
        "--acknowledge-local-session-storage",
        action="store_true",
        help="Confirm that the local storage-state file contains sensitive cookies.",
    )
    auth_login.set_defaults(handler=_handle_auth_login)
    auth_status = auth_subparsers.add_parser(
        "status",
        help="Show local authenticated-session metadata.",
    )
    auth_status.add_argument(
        "source",
        nargs="?",
        help="Source adapter to inspect. Defaults to the configured source.",
    )
    auth_status.set_defaults(handler=_handle_auth_status)
    auth_logout = auth_subparsers.add_parser(
        "logout",
        help="Delete local authenticated-session metadata and storage state.",
    )
    auth_logout.add_argument(
        "source",
        nargs="?",
        help="Source adapter to log out from. Defaults to the configured source.",
    )
    auth_logout.set_defaults(handler=_handle_auth_logout)
    auth_parser.set_defaults(handler=_handle_auth_help)

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
    ui_serve = ui_subparsers.add_parser(
        "serve",
        help="启动只监听 127.0.0.1 的本地 UI/API。",
    )
    ui_serve.add_argument(
        "--host",
        default="127.0.0.1",
        help="本地监听地址，仅支持 127.0.0.1。",
    )
    ui_serve.add_argument(
        "--port",
        type=int,
        default=8765,
        help="本地端口，默认 8765；测试可使用 0 自动分配。",
    )
    ui_serve.set_defaults(handler=_handle_ui_serve)
    ui_parser.set_defaults(handler=_handle_ui_help)

    download_parser = subparsers.add_parser(
        "download",
        help="Plan or run explicit local chapter downloads.",
    )
    download_subparsers = download_parser.add_subparsers(dest="download_command")
    download_plan = download_subparsers.add_parser(
        "plan",
        help="Preview local chapter download paths without fetching images.",
    )
    _add_download_common_arguments(download_plan)
    download_plan.set_defaults(handler=_handle_download_plan)
    download_run = download_subparsers.add_parser(
        "run",
        help="Save explicitly selected public chapter images locally.",
    )
    _add_download_common_arguments(download_run)
    download_run.set_defaults(handler=_handle_download_run)
    download_parser.set_defaults(handler=_handle_download_help)

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


def _add_download_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("source_comic_id", nargs="?", help="Saved local source comic id.")
    parser.add_argument(
        "--chapter",
        required=True,
        help="Local chapter title, source chapter id, order, local id, or URL.",
    )
    parser.add_argument(
        "--output-root",
        help="Download root directory. Defaults to the configured download_root.",
    )
    parser.add_argument(
        "--permission-note",
        required=True,
        help="Required note confirming user-authorized personal local archiving.",
    )
    parser.add_argument(
        "--auth",
        nargs="?",
        const=True,
        default=False,
        help="Use a saved local authenticated browser session to render the chapter page.",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Source adapter to use. Defaults to the configured source.",
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    search_fetcher_factory=None,
    sync_fetcher_factory=None,
    auth_login_runner=None,
    download_fetcher_factory=None,
    image_fetcher_factory=None,
    ui_server_factory=None,
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
            args.command == "auth"
            and getattr(args, "auth_command", None) == "login"
            and auth_login_runner is not None
        ):
            args.auth_login_runner = auth_login_runner
        if (
            args.command == "watch"
            and getattr(args, "watch_command", None) == "check"
            and sync_fetcher_factory is not None
        ):
            args.sync_fetcher_factory = sync_fetcher_factory
        if args.command == "download":
            if download_fetcher_factory is not None:
                args.download_fetcher_factory = download_fetcher_factory
            if image_fetcher_factory is not None:
                args.image_fetcher_factory = image_fetcher_factory
        if (
            args.command == "ui"
            and getattr(args, "ui_command", None) == "serve"
            and ui_server_factory is not None
        ):
            args.ui_server_factory = ui_server_factory
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

    try:
        factory = _search_fetcher_factory_for_args(args, config, source)
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
    except AuthSessionError as error:
        print(f"panelscout: auth search unavailable: {error}", file=sys.stderr)
        return 1
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
        auth_source = _sync_auth_source(args, source)
    except AuthSessionError as error:
        print(f"panelscout: auth sync unavailable: {error}", file=sys.stderr)
        return 1
    if auth_source is not None and auth_source != source:
        print(
            f"panelscout: sync auth source '{auth_source}' does not match sync source '{source}'",
            file=sys.stderr,
        )
        return 1
    if auth_source is not None and auth_source != SOURCE_NAME:
        print(f"panelscout: unsupported auth source '{auth_source}'", file=sys.stderr)
        return 1

    try:
        normalize_detail_reference(reference)
    except ValueError as error:
        print(f"panelscout: sync reference invalid: {error}", file=sys.stderr)
        return 1

    session = None
    if auth_source is not None:
        try:
            session = _require_auth_session(config, auth_source)
        except AuthSessionError as error:
            print(f"panelscout: auth sync unavailable: {error}", file=sys.stderr)
            return 1

    factory = getattr(args, "sync_fetcher_factory", None)
    if factory is None:
        if session is not None:
            factory = lambda runtime_config: _create_authenticated_detail_fetcher(
                runtime_config,
                session,
            )
        else:
            factory = _create_sync_fetcher
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
    except AuthSessionError as error:
        print(f"panelscout: auth sync failed: {error}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"panelscout: sync failed: {error}", file=sys.stderr)
        return 1

    print(
        _format_sync_result(
            result,
            saved=args.save,
            auth_source=auth_source,
            auth_status=session.status if session is not None else None,
        )
    )
    return 0


def _handle_auth_help(args: argparse.Namespace, config) -> int:
    print("panelscout auth login [SOURCE] --acknowledge-local-session-storage")
    print("panelscout auth status [SOURCE]")
    print("panelscout auth logout [SOURCE]")
    print("Login is user-driven in a local browser; PanelScout never stores plaintext passwords.")
    return 0


def _handle_auth_login(args: argparse.Namespace, config) -> int:
    source = _auth_source_from_args(args, config)
    if source != SOURCE_NAME:
        print(f"panelscout: unsupported auth source '{source}'", file=sys.stderr)
        return 1

    if not args.acknowledge_local_session_storage:
        print(
            "panelscout: auth login requires --acknowledge-local-session-storage "
            "because browser storage state contains sensitive cookies/session data",
            file=sys.stderr,
        )
        return 1

    try:
        start_url = (args.start_url or auth_start_url(source)).strip()
        session_path = _auth_session_path_from_args(args, config, source)
    except ValueError as error:
        print(f"panelscout: auth login failed: {error}", file=sys.stderr)
        return 1

    runner = getattr(args, "auth_login_runner", None) or run_manual_browser_login
    try:
        result = runner(
            source=source,
            start_url=start_url,
            session_path=session_path,
        )
        if result is None:
            result = BrowserLoginResult(source=source, session_path=session_path)
        stored_path = Path(result.session_path).expanduser()
        if not stored_path.exists():
            raise AuthSessionError("browser login did not create a session storage file")
        with connect_database(config.database_path) as connection:
            session = ComicRepository(connection).upsert_auth_session(
                AuthSession(
                    source=source,
                    storage_backend=result.storage_backend,
                    session_path=str(stored_path),
                    status=result.status,
                    warning_acknowledged_at=_utc_now_string(),
                )
            )
    except (AuthSessionError, OSError, ValueError) as error:
        print(f"panelscout: auth login failed: {error}", file=sys.stderr)
        return 1

    print(f"Auth session stored: {session.source}")
    print(f"Status: {session.status} (not server-validated)")
    print(f"Session file: {session.session_path}")
    print(f"Storage backend: {session.storage_backend}")
    print("PanelScout did not receive or store your username or password.")
    return 0


def _handle_auth_status(args: argparse.Namespace, config) -> int:
    source = _auth_source_from_args(args, config)
    if source != SOURCE_NAME:
        print(f"panelscout: unsupported auth source '{source}'", file=sys.stderr)
        return 1

    session = _load_auth_session_without_creating_database(config, source)
    print(_format_auth_status(session, source=source))
    return 0


def _handle_auth_logout(args: argparse.Namespace, config) -> int:
    source = _auth_source_from_args(args, config)
    if source != SOURCE_NAME:
        print(f"panelscout: unsupported auth source '{source}'", file=sys.stderr)
        return 1

    database_path = Path(config.database_path).expanduser()
    if str(config.database_path) != ":memory:" and not database_path.exists():
        print(f"No auth session configured for {source}.")
        return 0

    try:
        with connect_database(config.database_path) as connection:
            repository = ComicRepository(connection)
            session = repository.get_auth_session(source)
            if session is None:
                print(f"No auth session configured for {source}.")
                return 0

            deleted_file: Path | None = None
            missing_file: Path | None = None
            if session.session_path:
                session_file = Path(session.session_path).expanduser()
                if session_file.exists():
                    session_file.unlink()
                    deleted_file = session_file
                else:
                    missing_file = session_file

            repository.delete_auth_session(source)
    except OSError as error:
        print(f"panelscout: auth logout failed: {error}", file=sys.stderr)
        return 1

    print(f"Auth session removed: {source}")
    if deleted_file is not None:
        print(f"Deleted session file: {deleted_file}")
    elif missing_file is not None:
        print(f"Session file was already missing: {missing_file}")
    else:
        print("No session file was recorded.")
    return 0


def _create_authenticated_sync_fetcher(
    config,
    session: AuthSession,
    *,
    render_ready_selector: str | None = None,
    render_wait_seconds: float | None = None,
    render_image_snapshot: bool = False,
    render_click_texts: tuple[str, ...] = (),
    metadata_html_passthrough: bool = False,
):
    if not session.session_path:
        raise AuthSessionError("auth session metadata has no session file path")
    robots_policy = _load_zaimanhua_robots_policy(config)
    fetcher_options = {}
    if render_ready_selector is not None:
        fetcher_options["render_ready_selector"] = render_ready_selector
    if render_wait_seconds is not None:
        fetcher_options["render_wait_seconds"] = render_wait_seconds
    if render_image_snapshot:
        fetcher_options["render_image_snapshot"] = True
    if render_click_texts:
        fetcher_options["render_click_texts"] = render_click_texts
    if metadata_html_passthrough:
        fetcher_options["metadata_html_passthrough"] = True
    return AuthenticatedBrowserHtmlFetcher(
        config=config,
        session_path=session.session_path,
        robots_policy=robots_policy,
        **fetcher_options,
    )


def _create_authenticated_search_fetcher(config, session: AuthSession):
    return _create_authenticated_sync_fetcher(
        config,
        session,
        render_ready_selector='a[href*="/details/"]',
        render_wait_seconds=10,
    )


def _create_authenticated_detail_fetcher(config, session: AuthSession):
    return _create_authenticated_sync_fetcher(
        config,
        session,
        metadata_html_passthrough=True,
    )


def _create_search_fetcher(config):
    robots_policy = _load_zaimanhua_robots_policy(config)
    return HtmlFetcher(config=config, robots_policy=robots_policy)


def _create_sync_fetcher(config):
    robots_policy = _load_zaimanhua_robots_policy(config)
    return HtmlFetcher(config=config, robots_policy=robots_policy)


def _create_download_fetcher(config):
    return _create_sync_fetcher(config)


def _create_authenticated_download_fetcher(config, session: AuthSession):
    return _create_authenticated_sync_fetcher(
        config,
        session,
        render_ready_selector=CHAPTER_IMAGE_RENDER_SELECTOR,
        render_wait_seconds=10,
        render_click_texts=("滚动阅读",),
        render_image_snapshot=True,
    )


def _load_zaimanhua_robots_policy(config):
    return load_robots_policy(
        build_robots_url(),
        user_agent=config.user_agent,
    ).with_allowed_paths(
        (
            SEARCH_API_ROBOTS_ALLOW_PATH,
            DETAIL_API_ROBOTS_ALLOW_PATH,
            CHAPTER_DETAIL_API_ROBOTS_ALLOW_PATH,
        )
    )


def _create_image_fetcher(config):
    return ImageFetcher(config=config)


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


def _format_sync_result(
    result,
    *,
    saved: bool,
    auth_source: str | None = None,
    auth_status: str | None = None,
) -> str:
    comic = result.comic
    lines = [
        f"Synced detail: {comic.title}",
        f"Source URL: {result.detail_url}",
        f"id: {comic.source_comic_id}",
    ]
    if auth_source is not None:
        status = auth_status or "unknown"
        lines.append(f"Auth: {auth_source} ({status}; not server-validated)")
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


def _search_fetcher_factory_for_args(args: argparse.Namespace, config, source: str):
    injected_factory = getattr(args, "search_fetcher_factory", None)
    auth_source = _sync_auth_source(args, source)
    if auth_source is None:
        return injected_factory or _create_search_fetcher
    if auth_source != source:
        raise AuthSessionError(
            f"search auth source '{auth_source}' does not match search source '{source}'"
        )
    if auth_source != SOURCE_NAME:
        raise AuthSessionError(f"unsupported auth source '{auth_source}'")
    session = _require_auth_session(config, auth_source)
    if injected_factory is not None:
        return injected_factory
    return lambda runtime_config: _create_authenticated_search_fetcher(
        runtime_config,
        session,
    )


def _auth_source_from_args(args: argparse.Namespace, config) -> str:
    return (getattr(args, "source", None) or config.source).strip()


def _sync_auth_source(args: argparse.Namespace, sync_source: str) -> str | None:
    raw_auth = getattr(args, "auth", False)
    if raw_auth is False:
        return None
    if raw_auth is True:
        return sync_source
    auth_source = str(raw_auth).strip()
    if not auth_source:
        raise AuthSessionError("sync auth source cannot be blank")
    return auth_source


def _require_auth_session(config, source: str) -> AuthSession:
    if str(config.database_path) != ":memory:":
        database_path = Path(config.database_path).expanduser()
        if not database_path.exists():
            raise AuthSessionError(
                "auth session not configured; run auth login first"
            )

    with connect_database(config.database_path) as connection:
        session = ComicRepository(connection).get_auth_session(source)

    if session is None:
        raise AuthSessionError("auth session not configured; run auth login first")
    if not session.session_path:
        raise AuthSessionError("auth session metadata has no session file path")
    session_file = Path(session.session_path).expanduser()
    if not session_file.exists():
        raise AuthSessionError(f"auth session file missing: {session_file}")
    return session


def _auth_session_path_from_args(args: argparse.Namespace, config, source: str) -> Path:
    raw_path = getattr(args, "session_path", None)
    if raw_path is not None:
        if not str(raw_path).strip():
            raise ValueError("auth session path cannot be blank")
        return Path(raw_path).expanduser()
    return default_auth_session_path(config, source).expanduser()


def _load_auth_session_without_creating_database(config, source: str) -> AuthSession | None:
    if str(config.database_path) != ":memory:":
        database_path = Path(config.database_path).expanduser()
        if not database_path.exists():
            return None

    with connect_database(config.database_path) as connection:
        return ComicRepository(connection).get_auth_session(source)


def _format_auth_status(session: AuthSession | None, *, source: str) -> str:
    lines = [f"Auth session: {source}"]
    if session is None:
        lines.append("Status: not configured")
        lines.append("No local session metadata found.")
        return "\n".join(lines)

    session_file_exists = False
    if session.session_path:
        session_file_exists = Path(session.session_path).expanduser().exists()
    effective_status = (
        "missing_file"
        if session.session_path and not session_file_exists
        else session.status
    )

    lines.extend(
        [
            f"Status: {effective_status}",
            f"Stored status: {session.status}",
            f"Storage backend: {session.storage_backend}",
            f"Session file: {session.session_path or '(none)'}",
            f"Session file exists: {'yes' if session_file_exists else 'no'}",
            f"Created: {session.created_at or '(unknown)'}",
            f"Last validated: {session.last_validated_at or 'not server-validated'}",
            f"Expires hint: {session.expires_hint or 'unknown'}",
            (
                "Local storage warning acknowledged: "
                f"{session.warning_acknowledged_at or '(unknown)'}"
            ),
        ]
    )
    return "\n".join(lines)


def _utc_now_string() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


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
    print("panelscout ui serve [--port PORT]")
    print("build 生成本地静态 UI 文件；serve 启动 127.0.0.1 本地 UI/API。")
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


def _handle_ui_serve(args: argparse.Namespace, config) -> int:
    port = args.port
    if port < 0 or port > 65535:
        print("panelscout：ui serve 端口必须在 0 到 65535 之间", file=sys.stderr)
        return 1

    factory = getattr(args, "ui_server_factory", None) or serve_local_ui
    try:
        factory(config, host=args.host, port=port)
    except OSError as error:
        print(f"panelscout：ui serve 启动失败：{error}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"panelscout：ui serve 配置错误：{error}", file=sys.stderr)
        return 1
    return 0


def _handle_download_help(args: argparse.Namespace, config) -> int:
    print("panelscout download plan SOURCE_COMIC_ID --chapter REF [--output-root PATH] --permission-note NOTE")
    print("panelscout download run SOURCE_COMIC_ID --chapter REF [--output-root PATH] --permission-note NOTE")
    print("If --output-root is omitted, the configured download_root is used.")
    print("Downloads are explicit and local-only; no login, bypass, or background queue is started.")
    return 0


def _handle_download_plan(args: argparse.Namespace, config) -> int:
    loaded = _load_download_selection(args, config)
    if loaded is None:
        return 1
    source, comic, chapter = loaded

    try:
        factory = _download_fetcher_factory_for_args(args, config, source)
        download_root = _download_root_from_args(args, config)
        result = plan_public_chapter_download(
            comic=comic,
            chapter=chapter,
            chapter_fetcher=factory(config),
            download_root=download_root,
            permission_note=args.permission_note,
        )
    except AuthSessionError as error:
        print(f"panelscout: auth download unavailable: {error}", file=sys.stderr)
        return 1
    except (RobotsLoadError, RobotsDisallowedError, FetchError, ValueError) as error:
        print(f"panelscout: download plan failed: {error}", file=sys.stderr)
        return 1

    print(_format_download_plan_result(result, source=source))
    return 0


def _handle_download_run(args: argparse.Namespace, config) -> int:
    loaded = _load_download_selection(args, config)
    if loaded is None:
        return 1
    source, comic, chapter = loaded

    image_factory = getattr(args, "image_fetcher_factory", None) or _create_image_fetcher
    try:
        download_factory = _download_fetcher_factory_for_args(args, config, source)
        download_root = _download_root_from_args(args, config)
        result = save_public_chapter_download(
            comic=comic,
            chapter=chapter,
            chapter_fetcher=download_factory(config),
            image_fetcher=image_factory(config),
            download_root=download_root,
            permission_note=args.permission_note,
            max_image_workers=config.download_image_workers,
        )
    except AuthSessionError as error:
        print(f"panelscout: auth download unavailable: {error}", file=sys.stderr)
        return 1
    except (RobotsLoadError, RobotsDisallowedError, FetchError, ValueError) as error:
        print(f"panelscout: download run failed: {error}", file=sys.stderr)
        return 1

    print(_format_download_save_result(result, source=source))
    return 1 if result.failed_count else 0


def _load_download_selection(args: argparse.Namespace, config):
    source_comic_id = (args.source_comic_id or "").strip()
    if not source_comic_id:
        print("panelscout: download source comic id cannot be blank", file=sys.stderr)
        return None

    chapter_reference = (args.chapter or "").strip()
    if not chapter_reference:
        print("panelscout: download chapter reference cannot be blank", file=sys.stderr)
        return None

    if not (args.permission_note or "").strip():
        print("panelscout: download permission note cannot be blank", file=sys.stderr)
        return None

    source = args.source or config.source
    if source != SOURCE_NAME:
        print(f"panelscout: unsupported download source '{source}'", file=sys.stderr)
        return None

    database_path = Path(config.database_path).expanduser()
    if str(config.database_path) != ":memory:" and not database_path.exists():
        print(
            "panelscout: local database not found; run search --save and sync --save first",
            file=sys.stderr,
        )
        return None

    with connect_database(config.database_path) as connection:
        repository = ComicRepository(connection)
        comic = repository.get_comic_by_source(source, source_comic_id)
        if comic is None or comic.id is None:
            print(f"panelscout: local comic not found: {source_comic_id}", file=sys.stderr)
            return None
        chapter = _select_chapter(repository.list_chapters(comic.id), chapter_reference)
        if chapter is None:
            print(f"panelscout: local chapter not found: {chapter_reference}", file=sys.stderr)
            return None
        return source, comic, chapter


def _download_fetcher_factory_for_args(args: argparse.Namespace, config, source: str):
    injected_factory = getattr(args, "download_fetcher_factory", None)
    auth_source = _sync_auth_source(args, source)
    if auth_source is None:
        return injected_factory or _create_download_fetcher
    if auth_source != source:
        raise AuthSessionError(
            f"download auth source '{auth_source}' does not match download source '{source}'"
        )
    if auth_source != SOURCE_NAME:
        raise AuthSessionError(f"unsupported auth source '{auth_source}'")
    session = _require_auth_session(config, auth_source)
    if injected_factory is not None:
        return injected_factory
    return lambda runtime_config: _create_authenticated_download_fetcher(
        runtime_config,
        session,
    )


def _download_root_from_args(args: argparse.Namespace, config):
    raw_value = getattr(args, "output_root", None)
    if raw_value is None:
        return config.download_root
    if not str(raw_value).strip():
        raise ValueError("download output root cannot be blank")
    return raw_value


def _select_chapter(chapters, reference: str):
    normalized = reference.strip()
    for chapter in chapters:
        candidates = {
            chapter.title,
            chapter.chapter_url,
            str(chapter.id) if chapter.id is not None else "",
            str(chapter.chapter_order) if chapter.chapter_order is not None else "",
            chapter.source_chapter_id or "",
        }
        if normalized in candidates:
            return chapter
    return None


def _format_download_plan_result(result, *, source: str) -> str:
    plan = result.plan
    lines = [
        f"Download plan: {result.comic.title}",
        f"Source: {source}",
        f"Comic id: {result.comic.source_comic_id}",
        f"Chapter: {result.chapter.title}",
        f"Chapter URL: {result.chapter.chapter_url}",
        f"Permission note: {plan.permission_note}",
        f"Download root: {plan.download_root}",
        f"Chapter directory: {plan.chapter_directory}",
        f"Images discovered: {len(result.images)}",
        "No files were downloaded or written.",
        "",
        "Planned files:",
    ]
    for item in plan.items:
        lines.append(
            f"{item.page_number:03d}. {item.action}: {item.relative_path}"
        )
        lines.append(f"     source: {item.source_url}")
    return "\n".join(lines)


def _format_download_save_result(result, *, source: str) -> str:
    lines = [
        f"Download complete: {result.comic.title}",
        f"Source: {source}",
        f"Comic id: {result.comic.source_comic_id}",
        f"Chapter: {result.chapter.title}",
        f"Chapter directory: {result.plan.chapter_directory}",
        f"Saved: {result.saved_count}",
        f"Skipped: {result.skipped_count}",
        f"Failed: {result.failed_count}",
        "",
        "Files:",
    ]
    for item in result.items:
        lines.append(
            f"{item.plan_item.page_number:03d}. {item.status}: "
            f"{item.plan_item.relative_path}"
        )
        if item.bytes_written:
            lines.append(f"     bytes: {item.bytes_written}")
        if item.error:
            lines.append(f"     error: {item.error}")
    return "\n".join(lines)


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
