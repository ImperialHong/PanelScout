"""Local browser-session helpers for authenticated mode.

The helpers in this module never accept plaintext usernames or passwords.
Login must happen in a local browser controlled by the user, and only browser
storage state is saved for later authenticated requests.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import time
from typing import Callable
from urllib.parse import urlparse

from panelscout.adapters.zaimanhua import PUBLIC_BASE_URL, SOURCE_NAME
from panelscout.config import PanelScoutConfig
from panelscout.crawler.fetcher import (
    FetchBlockedError,
    FetchHTTPError,
    FetchedHtml,
    NonHtmlContentError,
)
from panelscout.crawler.robots import RobotsPolicy


DEFAULT_AUTH_STORAGE_BACKEND = "playwright_storage_state"
AUTH_SESSION_STATUS_STORED = "stored"
BLOCKED_STATUSES = {401, 403, 429}
HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
IMAGE_URL_PATTERN = re.compile(
    r"\.(?:jpg|jpeg|png|webp|gif|bmp|avif)(?:\?|$)",
    re.IGNORECASE,
)
CHAPTER_LINK_SELECTOR = '.zj_list_con a[href*="/view/"], a[href*="/view/"]'
CHAPTER_IMAGE_RENDER_SELECTOR = (
    'img[src*="images.zaimanhua.com"], '
    'img[data-src*="images.zaimanhua.com"], '
    'img[data-original*="images.zaimanhua.com"], '
    'img[data-url*="images.zaimanhua.com"], '
    'img[data-image*="images.zaimanhua.com"], '
    'img[data-lazy-src*="images.zaimanhua.com"], '
    'source[srcset*="images.zaimanhua.com"], '
    'source[data-srcset*="images.zaimanhua.com"]'
)
RENDERED_IMAGE_SNAPSHOT_SCRIPT = """
() => {
  const values = [];
  const append = value => {
    if (!value) {
      return;
    }
    const text = String(value).trim();
    if (!text) {
      return;
    }
    text.split(",").forEach(item => {
      const url = item.trim().split(/\\s+/, 1)[0];
      if (url) {
        values.push(url);
      }
    });
  };
  document.querySelectorAll("img, source").forEach(node => {
    append(node.currentSrc);
    [
      "src",
      "data-src",
      "data-original",
      "data-url",
      "data-image",
      "data-lazy-src",
      "srcset",
      "data-srcset"
    ].forEach(name => append(node.getAttribute(name)));
  });
  return Array.from(new Set(values));
}
"""


class AuthSessionError(RuntimeError):
    """Raised when local authenticated-session capture fails."""


class AuthSessionUnavailableError(AuthSessionError):
    """Raised when optional browser-login dependencies are unavailable."""


@dataclass(frozen=True, kw_only=True)
class BrowserLoginResult:
    """Result from a user-driven local browser login capture."""

    source: str
    session_path: Path
    storage_backend: str = DEFAULT_AUTH_STORAGE_BACKEND
    status: str = AUTH_SESSION_STATUS_STORED


def default_auth_session_path(config: PanelScoutConfig, source: str) -> Path:
    """Return the configured local browser storage-state path for a source."""

    return config.session_dir / f"{source}.storage.json"


def auth_start_url(source: str) -> str:
    """Return a conservative start URL for manual source login."""

    if source != SOURCE_NAME:
        raise ValueError(f"unsupported auth source: {source}")
    return PUBLIC_BASE_URL


def run_manual_browser_login(
    *,
    source: str,
    start_url: str,
    session_path: str | Path,
    input_func: Callable[[str], str] = input,
) -> BrowserLoginResult:
    """Open a local browser, let the user log in, then save storage state."""

    if source != SOURCE_NAME:
        raise ValueError(f"unsupported auth source: {source}")
    if not start_url.strip():
        raise ValueError("auth login start URL cannot be blank")

    path = Path(session_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    _capture_playwright_storage_state(
        start_url=start_url.strip(),
        session_path=path,
        input_func=input_func,
    )
    if not path.exists():
        raise AuthSessionError("browser login did not create a session storage file")

    return BrowserLoginResult(source=source, session_path=path)


def _capture_playwright_storage_state(
    *,
    start_url: str,
    session_path: Path,
    input_func: Callable[[str], str],
) -> None:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise AuthSessionUnavailableError(
            "Playwright is not installed. Install the optional auth dependencies "
            "and run `playwright install chromium`, then retry auth login."
        ) from error

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            page.goto(start_url, wait_until="domcontentloaded")
            input_func(
                "请在打开的本地浏览器中手动登录。完成登录和验证码后按 Enter 保存会话。"
            )
            context.storage_state(path=str(session_path))
            context.close()
            browser.close()
    except PlaywrightError as error:
        raise AuthSessionError(f"browser login failed: {error}") from error


class AuthenticatedBrowserHtmlFetcher:
    """Fetch HTML with a saved user-driven Playwright storage state."""

    def __init__(
        self,
        *,
        config: PanelScoutConfig,
        session_path: str | Path,
        robots_policy: RobotsPolicy | None = None,
        timeout_seconds: float = 20,
        render_wait_seconds: float = 5,
        render_ready_selector: str | None = CHAPTER_LINK_SELECTOR,
        render_scroll_to_bottom: bool = False,
        render_scroll_max_seconds: float = 20,
        render_scroll_min_rounds: int = 0,
        render_scroll_step_px: int = 1200,
        render_scroll_pause_seconds: float = 0.25,
        render_image_snapshot: bool = False,
        render_click_texts: tuple[str, ...] = (),
        request_delay_seconds: float | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self.user_agent = config.user_agent
        self.session_path = Path(session_path).expanduser()
        if not self.session_path.exists():
            raise AuthSessionError(f"auth session file missing: {self.session_path}")
        self.robots_policy = robots_policy
        self.timeout_seconds = timeout_seconds
        self.render_wait_seconds = render_wait_seconds
        self.render_ready_selector = render_ready_selector
        self.render_scroll_to_bottom = render_scroll_to_bottom
        self.render_scroll_max_seconds = render_scroll_max_seconds
        self.render_scroll_min_rounds = render_scroll_min_rounds
        self.render_scroll_step_px = render_scroll_step_px
        self.render_scroll_pause_seconds = render_scroll_pause_seconds
        self.render_image_snapshot = render_image_snapshot
        self.render_click_texts = render_click_texts
        self.request_delay_seconds = (
            request_delay_seconds
            if request_delay_seconds is not None
            else config.request_delay_seconds
        )
        self._sleep = sleeper
        self._monotonic = monotonic
        self._last_fetch_by_host: dict[str, float] = {}

    def fetch_html(self, url: str) -> FetchedHtml:
        """Fetch URL text with saved local session state and robots checks."""

        if self.robots_policy is not None:
            self.robots_policy.assert_allowed(url, user_agent=self.user_agent)

        self._respect_delay(url)
        fetched = self._fetch_with_playwright(url)
        self._last_fetch_by_host[_host_key(url)] = self._monotonic()
        return fetched

    def crawl_delay(self) -> float:
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

    def _fetch_with_playwright(self, url: str) -> FetchedHtml:
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise AuthSessionUnavailableError(
                "Playwright is not installed. Install the optional auth dependencies "
                "and run `playwright install chromium`, then retry authenticated sync."
            ) from error

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(
                    storage_state=str(self.session_path),
                    user_agent=self.user_agent,
                )
                page = context.new_page()
                rendered_image_values: list[str] = []
                if self.render_image_snapshot:
                    page.on("response", lambda response: _record_image_response(
                        response,
                        rendered_image_values,
                    ))
                try:
                    response = page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=int(self.timeout_seconds * 1000),
                    )
                    render_timeout_ms = int(self.render_wait_seconds * 1000)
                    try:
                        page.wait_for_load_state(
                            "networkidle",
                            timeout=render_timeout_ms,
                        )
                    except PlaywrightTimeoutError:
                        pass
                    if self.render_click_texts:
                        self._click_render_texts(
                            page,
                            PlaywrightTimeoutError,
                            timeout_ms=render_timeout_ms,
                        )
                    if self.render_ready_selector:
                        try:
                            page.wait_for_selector(
                                self.render_ready_selector,
                                timeout=render_timeout_ms,
                            )
                        except PlaywrightTimeoutError:
                            pass
                    if self.render_scroll_to_bottom:
                        self._scroll_to_bottom(
                            page,
                            PlaywrightTimeoutError,
                            rendered_image_values=rendered_image_values,
                        )
                    status_code = int(response.status) if response is not None else 200
                    headers = response.headers if response is not None else {}
                    content_type = str(headers.get("content-type", "text/html"))
                    if status_code in BLOCKED_STATUSES:
                        raise FetchBlockedError(
                            f"Server blocked authenticated request with status {status_code}"
                        )
                    if status_code >= 400:
                        raise FetchHTTPError(f"HTTP error {status_code}")
                    if not _is_html_content_type(content_type):
                        raise NonHtmlContentError(
                            f"Expected HTML response, got {content_type or 'unknown'}"
                        )
                    html = page.content()
                    if self.render_image_snapshot:
                        html = _append_rendered_image_snapshot(
                            page,
                            html,
                            extra_values=rendered_image_values,
                        )
                    return FetchedHtml(
                        url=url,
                        status_code=status_code,
                        content_type=content_type,
                        text=html,
                    )
                finally:
                    context.close()
                    browser.close()
        except (FetchBlockedError, FetchHTTPError, NonHtmlContentError):
            raise
        except PlaywrightTimeoutError as error:
            raise AuthSessionError(f"authenticated sync timed out: {error}") from error
        except PlaywrightError as error:
            raise AuthSessionError(f"authenticated sync failed: {error}") from error

    def _click_render_texts(
        self,
        page,
        timeout_error_type: type[Exception],
        *,
        timeout_ms: int,
    ) -> None:
        for text in self.render_click_texts:
            try:
                page.get_by_text(text, exact=True).first.click(timeout=timeout_ms)
            except timeout_error_type:
                try:
                    page.get_by_text(text, exact=False).first.click(timeout=1000)
                except timeout_error_type:
                    continue
            try:
                page.wait_for_load_state("networkidle", timeout=timeout_ms)
            except timeout_error_type:
                pass

    def _scroll_to_bottom(
        self,
        page,
        timeout_error_type: type[Exception],
        *,
        rendered_image_values: list[str],
    ) -> None:
        deadline = self._monotonic() + max(0.0, self.render_scroll_max_seconds)
        min_rounds = max(0, int(self.render_scroll_min_rounds))
        step_px = max(1, int(self.render_scroll_step_px))
        pause_ms = max(0, int(self.render_scroll_pause_seconds * 1000))
        stable_rounds = 0
        previous_signature: tuple[int, int, int] | None = None
        rounds = 0

        while True:
            rounds += 1
            page.mouse.move(640, 360)
            page.mouse.wheel(0, step_px)
            page.evaluate("(step) => window.scrollBy(0, step)", step_px)
            if pause_ms:
                page.wait_for_timeout(pause_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=1000)
            except timeout_error_type:
                pass
            rendered_image_values.extend(_rendered_image_values(page))

            metrics = page.evaluate(
                """
                selector => {
                  const root = document.documentElement;
                  const body = document.body || root;
                  const height = Math.max(
                    root.scrollHeight,
                    body.scrollHeight,
                    root.offsetHeight,
                    body.offsetHeight,
                    root.clientHeight
                  );
                  const viewport = window.innerHeight || root.clientHeight || 0;
                  const y = window.scrollY || window.pageYOffset || 0;
                  const count = selector
                    ? document.querySelectorAll(selector).length
                    : document.querySelectorAll("img, source").length;
                  return {
                    scrollHeight: height,
                    viewportHeight: viewport,
                    scrollY: y,
                    imageCount: count
                  };
                }
                """,
                self.render_ready_selector,
            )
            signature = (
                int(metrics["scrollHeight"]),
                int(metrics["scrollY"]),
                len(set(rendered_image_values)) or int(metrics["imageCount"]),
            )
            at_bottom = (
                int(metrics["scrollY"]) + int(metrics["viewportHeight"])
                >= int(metrics["scrollHeight"]) - 2
            )
            if at_bottom and previous_signature == signature:
                stable_rounds += 1
            else:
                stable_rounds = 0
            if at_bottom and stable_rounds >= 2 and rounds >= min_rounds:
                break
            if self._monotonic() >= deadline:
                break
            previous_signature = signature


def _append_rendered_image_snapshot(
    page,
    html: str,
    *,
    extra_values: list[str],
) -> str:
    image_values = extra_values + _rendered_image_values(page)
    image_values = [value for value in dict.fromkeys(image_values) if value]
    if not image_values:
        return html
    snapshot = json.dumps(image_values, ensure_ascii=False)
    return (
        f"{html}\n"
        f"<script type=\"application/json\">"
        f"window.__PANELSCOUT_CHAPTER_IMAGES__ = {snapshot};"
        f"</script>"
    )


def _rendered_image_values(page) -> list[str]:
    raw_values = page.evaluate(RENDERED_IMAGE_SNAPSHOT_SCRIPT)
    if not isinstance(raw_values, list):
        return []
    return [str(value).strip() for value in raw_values if str(value).strip()]


def _record_image_response(response, image_values: list[str]) -> None:
    try:
        content_type = str(response.headers.get("content-type", ""))
        if content_type.lower().startswith("image/") or IMAGE_URL_PATTERN.search(
            response.url
        ):
            image_values.append(response.url)
    except Exception:
        return


def _host_key(url: str) -> str:
    return urlparse(url).netloc.lower()


def _is_html_content_type(content_type: str) -> bool:
    normalized = content_type.split(";", 1)[0].strip().lower()
    return normalized in HTML_CONTENT_TYPES
