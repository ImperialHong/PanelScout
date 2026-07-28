"""Double-click friendly Windows launcher for the local PanelScout UI."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
import os
from pathlib import Path
import socket
import sys
import threading
import time
import webbrowser

from panelscout.config import ConfigError, load_config
from panelscout.ui.server import serve_local_ui

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
OPEN_TIMEOUT_SECONDS = 15.0


def main(
    argv: Sequence[str] | None = None,
    *,
    browser_open: Callable[[str], bool] | None = None,
    server_runner: Callable[..., None] | None = None,
) -> int:
    """Start the local UI and open it in the user's default browser."""

    args = _build_parser().parse_args(argv)
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")

    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"PanelScout config error: {error}", file=sys.stderr)
        _pause_if_interactive(args.pause_on_exit)
        return 1

    url = f"http://{args.host}:{args.port}/"
    opener = browser_open or webbrowser.open
    runner = server_runner or serve_local_ui

    if not args.no_browser:
        thread = threading.Thread(
            target=_open_browser_when_ready,
            args=(url, args.host, args.port, opener),
            daemon=True,
        )
        thread.start()

    print(f"PanelScout will open at {url}")
    print("Keep this window open while using PanelScout. Close it to stop the app.")
    try:
        runner(config, host=args.host, port=args.port)
    except OSError as error:
        print(f"PanelScout failed to start: {error}", file=sys.stderr)
        _pause_if_interactive(args.pause_on_exit)
        return 1
    except ValueError as error:
        print(f"PanelScout server error: {error}", file=sys.stderr)
        _pause_if_interactive(args.pause_on_exit)
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="PanelScout",
        description="Start the PanelScout local UI.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional PanelScout config.toml path.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help="Local UI host. Keep the default unless debugging.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Local UI port.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Start the UI without opening the default browser.",
    )
    parser.add_argument(
        "--no-pause-on-exit",
        action="store_false",
        dest="pause_on_exit",
        help="Do not wait for Enter after startup errors.",
    )
    parser.set_defaults(pause_on_exit=True)
    return parser


def _open_browser_when_ready(
    url: str,
    host: str,
    port: int,
    opener: Callable[[str], bool],
) -> None:
    deadline = time.monotonic() + OPEN_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if _is_port_open(host, port):
            opener(url)
            return
        time.sleep(0.2)
    opener(url)


def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


def _pause_if_interactive(should_pause: bool) -> None:
    if should_pause and sys.stdin.isatty():
        input("Press Enter to exit...")


if __name__ == "__main__":
    raise SystemExit(main())
