"""Injectable binary image fetcher for explicit downloads."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, build_opener

from panelscout.config import DEFAULT_USER_AGENT, PanelScoutConfig
from panelscout.crawler.fetcher import FetchBlockedError, FetchError, FetchHTTPError

BLOCKED_STATUSES = {401, 403, 429}


@dataclass(frozen=True, kw_only=True)
class FetchedImage:
    """Fetched image bytes with response metadata."""

    url: str
    status_code: int
    content_type: str
    content: bytes


class ImageFetcher:
    """Fetch image bytes through an injectable opener.

    This fetcher sends only a clear User-Agent and generic image Accept header.
    It does not add referer headers, cookies, sessions, or any anti-hotlinking
    bypass behavior.
    """

    def __init__(
        self,
        *,
        config: PanelScoutConfig | None = None,
        user_agent: str | None = None,
        opener: Any | None = None,
        timeout_seconds: float = 30,
        request_delay_seconds: float | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.user_agent = user_agent or (config.user_agent if config else DEFAULT_USER_AGENT)
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

    def fetch_image(self, url: str) -> FetchedImage:
        self._respect_delay(url)
        request = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            },
        )
        try:
            response = self._open(request)
        except HTTPError as error:
            if error.code in BLOCKED_STATUSES:
                raise FetchBlockedError(f"Server blocked image request with status {error.code}") from error
            raise FetchHTTPError(f"HTTP image error {error.code}") from error

        status_code = _response_status(response)
        if status_code in BLOCKED_STATUSES:
            raise FetchBlockedError(f"Server blocked image request with status {status_code}")
        if status_code >= 400:
            raise FetchHTTPError(f"HTTP image error {status_code}")

        content_type = _response_header(response, "Content-Type")
        if not _is_image_content_type(content_type):
            raise NonImageContentError(
                f"Expected image response, got {content_type or 'unknown'}"
            )

        content = response.read()
        self._last_fetch_by_host[_host_key(url)] = self._monotonic()
        if not content:
            raise FetchError("Image response was empty")
        return FetchedImage(
            url=url,
            status_code=status_code,
            content_type=content_type,
            content=content,
        )

    def _respect_delay(self, url: str) -> None:
        delay = float(self.request_delay_seconds or 0)
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


class NonImageContentError(FetchError):
    """Raised when a response is not an image."""


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


def _is_image_content_type(content_type: str) -> bool:
    normalized = content_type.split(";", 1)[0].strip().lower()
    return normalized.startswith("image/") or normalized == "application/octet-stream"


def _host_key(url: str) -> str:
    return urlparse(url).netloc.lower()
