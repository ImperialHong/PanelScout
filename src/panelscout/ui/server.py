"""Local-only HTTP runner for the interactive PanelScout UI."""

from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from typing import Any
from urllib.parse import parse_qs, urlparse

from panelscout.config import PanelScoutConfig
from panelscout.ui.api import PanelScoutUiApi, UiApiError, UiApiFactories
from panelscout.ui.app_shell import build_interactive_ui_shell
from panelscout.ui.state import build_local_ui_state


ALLOWED_UI_HOSTS = {"127.0.0.1"}


class UiServerError(ValueError):
    """Raised when the local UI runner configuration is unsafe."""


@dataclass(frozen=True, kw_only=True)
class UiHttpResponse:
    status_code: int
    content_type: str
    body: bytes


class UiHttpApplication:
    """Testable HTTP application used by the local runner."""

    def __init__(self, config: PanelScoutConfig, *, api: PanelScoutUiApi | None = None) -> None:
        self.config = config
        self.api = api or PanelScoutUiApi(config)

    def dispatch(self, method: str, raw_path: str, body: bytes = b"") -> UiHttpResponse:
        parsed = urlparse(raw_path)
        try:
            if method == "GET" and parsed.path == "/":
                html = build_interactive_ui_shell(build_local_ui_state(self.config))
                return _html_response(html)
            if method == "GET" and parsed.path == "/api/state":
                return _json_response(self.api.state())
            if method == "GET" and parsed.path == "/api/download/status":
                payload = {
                    key: values[-1]
                    for key, values in parse_qs(parsed.query, keep_blank_values=True).items()
                }
                return _json_response(self.api.download_status(payload))
            if method == "POST":
                payload = _json_payload(body)
                if parsed.path == "/api/search":
                    return _json_response(self.api.search(payload))
                if parsed.path == "/api/sync":
                    return _json_response(self.api.sync(payload))
                if parsed.path == "/api/download/plan":
                    return _json_response(self.api.download_plan(payload))
                if parsed.path == "/api/download/run":
                    return _json_response(self.api.download_run(payload))
                if parsed.path == "/api/download/status":
                    return _json_response(self.api.download_status(payload))
        except UiApiError as error:
            return _json_response(
                {"ok": False, "error": str(error)},
                status_code=error.status_code,
            )
        except json.JSONDecodeError as error:
            return _json_response(
                {"ok": False, "error": f"invalid JSON: {error.msg}"},
                status_code=400,
            )

        return _json_response({"ok": False, "error": "not found"}, status_code=404)


def serve_local_ui(
    config: PanelScoutConfig,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    api: PanelScoutUiApi | None = None,
) -> None:
    """Serve the interactive UI in the foreground on a local-only host."""

    if host not in ALLOWED_UI_HOSTS:
        raise UiServerError("ui serve only supports 127.0.0.1")
    if port < 0 or port > 65535:
        raise UiServerError("ui serve port must be between 0 and 65535")

    app = UiHttpApplication(config, api=api)
    handler = _handler_factory(app)
    server = HTTPServer((host, port), handler)
    actual_host, actual_port = server.server_address
    print(f"PanelScout UI: http://{actual_host}:{actual_port}")
    print("本地 UI 服务运行中；按 Ctrl+C 停止。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPanelScout UI 已停止。")
    finally:
        server.server_close()


def make_ui_api(
    config: PanelScoutConfig,
    *,
    factories: UiApiFactories | None = None,
) -> PanelScoutUiApi:
    return PanelScoutUiApi(config, factories=factories)


def _handler_factory(app: UiHttpApplication):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib callback name.
            self._send(app.dispatch("GET", self.path))

        def do_POST(self) -> None:  # noqa: N802 - stdlib callback name.
            length = int(self.headers.get("Content-Length", "0") or "0")
            self._send(app.dispatch("POST", self.path, self.rfile.read(length)))

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

        def _send(self, response: UiHttpResponse) -> None:
            self.send_response(response.status_code)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            self.end_headers()
            self.wfile.write(response.body)

    return Handler


def _html_response(html: str, *, status_code: int = 200) -> UiHttpResponse:
    return UiHttpResponse(
        status_code=status_code,
        content_type="text/html; charset=utf-8",
        body=html.encode("utf-8"),
    )


def _json_response(payload: dict[str, Any], *, status_code: int = 200) -> UiHttpResponse:
    return UiHttpResponse(
        status_code=status_code,
        content_type="application/json; charset=utf-8",
        body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )


def _json_payload(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    decoded = json.loads(body.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise UiApiError("request body must be a JSON object", status_code=400)
    return decoded
