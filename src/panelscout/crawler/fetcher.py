"""Injectable HTML fetcher baseline with robots checks."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, build_opener

from panelscout.config import DEFAULT_USER_AGENT, PanelScoutConfig
from panelscout.crawler.robots import RobotsPolicy

BLOCKED_STATUSES = {401, 403, 429}
HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")


@dataclass(frozen=True)
class FetchedHtml:
    """Fetched HTML text with response metadata."""

    url: str
    status_code: int
    content_type: str
    text: str


class HtmlFetcher:
    """Fetch public HTML through an injectable opener.

    The default opener uses urllib, but tests and future crawler code can inject
    any callable or object exposing an ``open`` method. This class performs no
    site-specific parsing.
    """

    def __init__(
        self,
        *,
        config: PanelScoutConfig | None = None,
        user_agent: str | None = None,
        robots_policy: RobotsPolicy | None = None,
        opener: Any | None = None,
        timeout_seconds: float = 20,
        request_delay_seconds: float | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.user_agent = user_agent or (config.user_agent if config else DEFAULT_USER_AGENT)
        self.robots_policy = robots_policy
        self.opener = opener or build_opener()
        self.timeout_seconds = timeout_seconds
        self.request_delay_seconds = (
            request_delay_seconds
            if request_delay_seconds is not None
            else (config.request_delay_seconds if config else 0)
        )
        self._sleep = sleeper
        self._monotonic = monotonic
        self._last_fetch_by_host: dict[str, float] = {}

    def fetch_html(self, url: str) -> FetchedHtml:
        """Fetch URL text after robots and response safety checks."""

        if self.robots_policy is not None:
            self.robots_policy.assert_allowed(url, user_agent=self.user_agent)

        self._respect_delay(url)
        request = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml",
            },
        )

        try:
            response = self._open(request)
        except HTTPError as error:
            if error.code in BLOCKED_STATUSES:
                raise FetchBlockedError(f"Server blocked request with status {error.code}") from error
            raise FetchHTTPError(f"HTTP error {error.code}") from error

        status_code = _response_status(response)
        if status_code in BLOCKED_STATUSES:
            raise FetchBlockedError(f"Server blocked request with status {status_code}")
        if status_code >= 400:
            raise FetchHTTPError(f"HTTP error {status_code}")

        content_type = _response_header(response, "Content-Type")
        if not _is_html_content_type(content_type):
            raise NonHtmlContentError(f"Expected HTML response, got {content_type or 'unknown'}")

        raw_body = response.read()
        self._last_fetch_by_host[_host_key(url)] = self._monotonic()
        return FetchedHtml(
            url=url,
            status_code=status_code,
            content_type=content_type,
            text=raw_body.decode(_charset_from_content_type(content_type), errors="replace"),
        )

    def crawl_delay(self) -> float:
        """Return the effective delay this fetcher will apply between requests."""

        robots_delay = (
            self.robots_policy.crawl_delay(user_agent=self.user_agent)
            if self.robots_policy is not None
            else None
        )
        if robots_delay is not None:
            return robots_delay
        return float(self.request_delay_seconds or 0)

    def _respect_delay(self, url: str) -> None:
        delay = self.crawl_delay()
        if delay <= 0:
            return

        host = _host_key(url)
        last_fetch_at = self._last_fetch_by_host.get(host)
        if last_fetch_at is None:
            return

        elapsed = self._monotonic() - last_fetch_at
        remaining = delay - elapsed
        if remaining > 0:
            self._sleep(remaining)

    def _open(self, request: Request) -> Any:
        if callable(self.opener):
            return self.opener(request, timeout=self.timeout_seconds)
        return self.opener.open(request, timeout=self.timeout_seconds)


class FetchError(RuntimeError):
    """Base class for fetcher failures."""


class FetchBlockedError(FetchError):
    """Raised when the server returns a blocked/limited status."""


class FetchHTTPError(FetchError):
    """Raised for non-success HTTP status codes."""


class NonHtmlContentError(FetchError):
    """Raised when a response is not HTML."""


def _response_status(response: Any) -> int:
    if getattr(response, "status", None) is not None:
        return int(response.status)
    if hasattr(response, "getcode"):
        return int(response.getcode())
    return 200


def _response_header(response: Any, header: str) -> str:
    if hasattr(response, "headers") and response.headers is not None:
        value = response.headers.get(header)
        if value is not None:
            return str(value)
    if hasattr(response, "info"):
        info = response.info()
        if hasattr(info, "get"):
            value = info.get(header)
            if value is not None:
                return str(value)
    return ""


def _is_html_content_type(content_type: str) -> bool:
    normalized = content_type.split(";", 1)[0].strip().lower()
    return normalized in HTML_CONTENT_TYPES


def _charset_from_content_type(content_type: str) -> str:
    for part in content_type.split(";")[1:]:
        key, _, value = part.strip().partition("=")
        if key.lower() == "charset" and value:
            return value.strip()
    return "utf-8"


def _host_key(url: str) -> str:
    return urlparse(url).netloc.lower()
