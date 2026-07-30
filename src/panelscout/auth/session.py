"""Local browser-session helpers for authenticated mode.

Manual login is still user-driven in a local browser. Credential login accepts
plaintext only for the active local request, sends it to the configured source
login form, and persists only browser storage state for later requests.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import json
from pathlib import Path
import re
import time
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlparse
from urllib.request import Request, build_opener

from panelscout.adapters.zaimanhua import PUBLIC_BASE_URL, SOURCE_NAME
from panelscout.config import PanelScoutConfig
from panelscout.crawler.fetcher import (
    FetchBlockedError,
    FetchHTTPError,
    FetchedHtml,
    HtmlFetcher,
    NonHtmlContentError,
)
from panelscout.crawler.robots import RobotsPolicy


DEFAULT_AUTH_STORAGE_BACKEND = "playwright_storage_state"
AUTH_SESSION_STATUS_STORED = "stored"
BLOCKED_STATUSES = {401, 403, 429}
HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
JSON_CONTENT_TYPES = ("application/json", "text/json", "application/problem+json")
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
    user_id: str | None = None


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


def run_browser_credential_login(
    *,
    source: str,
    start_url: str,
    session_path: str | Path,
    username: str,
    password: str,
    headless: bool = True,
) -> BrowserLoginResult:
    """Submit credentials in a local browser and save browser storage state."""

    if source != SOURCE_NAME:
        raise ValueError(f"unsupported auth source: {source}")
    if not start_url.strip():
        raise ValueError("auth login start URL cannot be blank")

    user_id = str(username).strip()
    if not user_id:
        raise ValueError("auth login username cannot be blank")
    password_text = str(password)
    if not password_text:
        raise ValueError("auth login password cannot be blank")

    path = Path(session_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    _capture_playwright_storage_state_with_credentials(
        start_url=start_url.strip(),
        session_path=path,
        username=user_id,
        password=password_text,
        headless=headless,
    )
    if not path.exists():
        raise AuthSessionError("browser login did not create a session storage file")

    return BrowserLoginResult(source=source, session_path=path, user_id=user_id)


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


def _capture_playwright_storage_state_with_credentials(
    *,
    start_url: str,
    session_path: Path,
    username: str,
    password: str,
    headless: bool,
) -> None:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise AuthSessionUnavailableError(
            "Playwright is not installed. Install the optional auth dependencies "
            "and run `playwright install chromium`, then retry auth login."
        ) from error

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=headless)
            context = browser.new_context()
            page = context.new_page()
            try:
                page.goto(start_url, wait_until="domcontentloaded", timeout=20_000)
                _dismiss_initial_overlays(page)
                _open_login_form(page)
                _fill_login_form(page, username=username, password=password)
                _wait_for_login_completion(page)
                try:
                    page.wait_for_load_state("networkidle", timeout=10_000)
                except PlaywrightTimeoutError:
                    pass
                context.storage_state(path=str(session_path))
            finally:
                context.close()
                browser.close()
    except PlaywrightError as error:
        raise AuthSessionError(f"browser credential login failed: {error}") from error


def _open_login_form(page) -> None:
    if _password_input_count(page) > 0:
        return

    for selector in (
        ".tplogin",
        "text=登录",
        "p:has-text('登录')",
        "button:has-text('登录')",
        "[class*='login']",
        "[class*='Login']",
    ):
        try:
            page.locator(selector).first.click(timeout=2_000)
            page.wait_for_selector("input[type='password']", timeout=3_000)
        except Exception:  # noqa: BLE001 - try the next source-login affordance.
            continue
        if _password_input_count(page) > 0:
            return


def _dismiss_initial_overlays(page) -> None:
    page.wait_for_timeout(1_000)
    for selector in (
        ".teenbtn",
        "text=我知道了",
    ):
        try:
            page.wait_for_selector(selector, timeout=3_000)
            locator = page.locator(selector).first
            if locator.is_visible():
                locator.click(timeout=2_000)
                page.wait_for_timeout(500)
        except Exception:  # noqa: BLE001 - overlay may be absent on repeat visits.
            continue


def _fill_login_form(page, *, username: str, password: str) -> None:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    try:
        password_input = page.locator(
            ".login_pop input[type='password'], input[type='password']"
        ).first
        password_input.wait_for(timeout=8_000)
    except PlaywrightTimeoutError as error:
        raise AuthSessionError("login password input was not found") from error

    username_input = _first_visible_locator(
        page,
        (
            ".login_pop input[placeholder*='用户名']",
            ".login_pop input[type='text']",
            "input[name='username']",
            "input[name='user']",
            "input[name='account']",
            "input[name='phone']",
            "input[type='tel']",
            "input[type='email']",
            "input[type='text']",
        ),
    )
    if username_input is None:
        raise AuthSessionError("login username input was not found")

    username_input.fill(username)
    password_input.fill(password)
    submitted = False
    for selector in (
        ".login_pop button.lg_button",
        ".login_pop button:has-text('登录')",
        ".login_pop .lg_button",
        "button[type='submit']",
        "button:has-text('登录')",
        "a:has-text('登录')",
        "[class*='submit']",
        "[class*='login']",
    ):
        try:
            page.locator(selector).first.click(timeout=2_000)
            submitted = True
            break
        except Exception:  # noqa: BLE001 - fall back to pressing Enter.
            continue
    if not submitted:
        password_input.press("Enter")


def _wait_for_login_completion(page) -> None:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    try:
        page.wait_for_function(
            "() => document.body && document.body.innerText.includes('个人中心')",
            timeout=12_000,
        )
    except PlaywrightTimeoutError as error:
        raise AuthSessionError("login did not reach authenticated page state") from error


def _password_input_count(page) -> int:
    try:
        return page.locator("input[type='password']").count()
    except Exception:  # noqa: BLE001 - caller will continue probing.
        return 0


def _first_visible_locator(page, selectors: tuple[str, ...]):
    for selector in selectors:
        locator = page.locator(selector)
        for index in range(locator.count()):
            candidate = locator.nth(index)
            try:
                if candidate.is_visible(timeout=500):
                    return candidate
            except Exception:  # noqa: BLE001 - try the next candidate.
                continue
    return None


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
        render_image_snapshot: bool = False,
        render_click_texts: tuple[str, ...] = (),
        metadata_html_passthrough: bool = False,
        json_opener: Any | None = None,
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
        self.render_image_snapshot = render_image_snapshot
        self.render_click_texts = render_click_texts
        self.metadata_html_passthrough = metadata_html_passthrough
        self.json_opener = json_opener or build_opener()
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
        if self.metadata_html_passthrough and _is_detail_page_url(url):
            fetched = self._fetch_public_html(url)
        else:
            fetched = self._fetch_with_playwright(url)
        self._last_fetch_by_host[_host_key(url)] = self._monotonic()
        return fetched

    def fetch_json(self, url: str) -> FetchedHtml:
        """Fetch front-end JSON metadata with saved local session cookies."""

        if self.robots_policy is not None:
            self.robots_policy.assert_allowed(url, user_agent=self.user_agent)

        self._respect_delay(url)
        fetched = self._fetch_json_with_storage_state(url)
        self._last_fetch_by_host[_host_key(url)] = self._monotonic()
        return fetched

    def _fetch_public_html(self, url: str) -> FetchedHtml:
        fetcher = HtmlFetcher(
            config=self.config,
            robots_policy=self.robots_policy,
            timeout_seconds=self.timeout_seconds,
            request_delay_seconds=0,
            sleeper=self._sleep,
            monotonic=self._monotonic,
        )
        return fetcher.fetch_html(url)

    def _fetch_json_with_storage_state(self, url: str) -> FetchedHtml:
        storage_state = _read_storage_state(self.session_path)
        token = _storage_state_token(storage_state, url)
        request_url = _api_url_with_session_identity(url, token)
        cookie_header = _storage_state_cookie_header_from_payload(storage_state, request_url)
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json,text/json,*/*",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
            headers["Platform"] = "pc"
        if cookie_header:
            headers["Cookie"] = cookie_header
        request = Request(request_url, headers=headers)
        try:
            response = _open(self.json_opener, request, self.timeout_seconds)
        except HTTPError as error:
            if error.code in BLOCKED_STATUSES:
                raise FetchBlockedError(
                    f"Server blocked authenticated request with status {error.code}"
                ) from error
            raise FetchHTTPError(f"HTTP error {error.code}") from error

        status_code = _response_status(response)
        if status_code in BLOCKED_STATUSES:
            raise FetchBlockedError(f"Server blocked authenticated request with status {status_code}")
        if status_code >= 400:
            raise FetchHTTPError(f"HTTP error {status_code}")

        content_type = _response_header(response, "Content-Type")
        if not _is_json_content_type(content_type):
            raise NonHtmlContentError(f"Expected JSON response, got {content_type or 'unknown'}")
        raw_body = response.read()
        return FetchedHtml(
            url=request_url,
            status_code=status_code,
            content_type=content_type,
            text=raw_body.decode(_charset_from_content_type(content_type), errors="replace"),
        )

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


def _storage_state_cookie_header(session_path: Path, url: str) -> str:
    return _storage_state_cookie_header_from_payload(_read_storage_state(session_path), url)


def _read_storage_state(session_path: Path) -> dict[str, object]:
    try:
        payload = json.loads(session_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AuthSessionError(f"auth session file could not be read: {session_path}") from error
    return payload if isinstance(payload, dict) else {}


def _storage_state_cookie_header_from_payload(payload: dict[str, object], url: str) -> str:
    cookies = payload.get("cookies") if isinstance(payload, dict) else None
    if not isinstance(cookies, list):
        return ""

    parsed = urlparse(url)
    pairs = []
    for cookie in cookies:
        if not isinstance(cookie, dict) or not _cookie_matches_url(cookie, parsed):
            continue
        name = str(cookie.get("name") or "").strip()
        value = str(cookie.get("value") or "")
        if name:
            pairs.append(f"{name}={value}")
    return "; ".join(pairs)


def _storage_state_token(payload: dict[str, object], url: str) -> str | None:
    parsed = urlparse(url)
    expected_origin = f"{parsed.scheme}://{parsed.netloc}"
    origins = payload.get("origins")
    if not isinstance(origins, list):
        return None
    for origin in origins:
        if not isinstance(origin, dict) or origin.get("origin") != expected_origin:
            continue
        local_storage = origin.get("localStorage")
        if not isinstance(local_storage, list):
            continue
        for item in local_storage:
            if not isinstance(item, dict) or item.get("name") != "token":
                continue
            token = str(item.get("value") or "").strip()
            return token or None
    return None


def _api_url_with_session_identity(url: str, token: str | None) -> str:
    uid = _uid_from_jwt(token)
    if uid is None:
        return url

    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "uid" in query:
        query["uid"] = uid
    if "timestamp" in query:
        query["timestamp"] = str(int(time.time() * 1000))
    return parsed._replace(query=urlencode(query)).geturl()


def _uid_from_jwt(token: str | None) -> str | None:
    if not token:
        return None
    parts = token.split(".")
    if len(parts) < 2:
        return None
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        decoded = json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
    except (binascii.Error, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return None
    uid = decoded.get("uid") if isinstance(decoded, dict) else None
    if uid is None:
        return None
    return str(uid)


def _cookie_matches_url(cookie: dict[str, object], parsed_url) -> bool:
    host = parsed_url.netloc.lower()
    domain = str(cookie.get("domain") or "").lstrip(".").lower()
    if not domain or (host != domain and not host.endswith(f".{domain}")):
        return False

    path = str(cookie.get("path") or "/")
    if not (parsed_url.path or "/").startswith(path):
        return False

    if bool(cookie.get("secure")) and parsed_url.scheme != "https":
        return False

    expires = cookie.get("expires")
    if isinstance(expires, int | float) and expires > 0 and expires < time.time():
        return False
    return True


def _open(opener, request: Request, timeout_seconds: float):
    if callable(opener):
        return opener(request, timeout=timeout_seconds)
    return opener.open(request, timeout=timeout_seconds)


def _response_status(response) -> int:
    if getattr(response, "status", None) is not None:
        return int(response.status)
    if hasattr(response, "getcode"):
        return int(response.getcode())
    return 200


def _response_header(response, header: str) -> str:
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


def _charset_from_content_type(content_type: str) -> str:
    for part in content_type.split(";")[1:]:
        key, _, value = part.strip().partition("=")
        if key.lower() == "charset" and value:
            return value.strip()
    return "utf-8"


def _host_key(url: str) -> str:
    return urlparse(url).netloc.lower()


def _is_detail_page_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.netloc.lower() == urlparse(PUBLIC_BASE_URL).netloc
        and parsed.path.startswith("/details/")
    )


def _is_html_content_type(content_type: str) -> bool:
    normalized = content_type.split(";", 1)[0].strip().lower()
    return normalized in HTML_CONTENT_TYPES


def _is_json_content_type(content_type: str) -> bool:
    normalized = content_type.split(";", 1)[0].strip().lower()
    return normalized in JSON_CONTENT_TYPES
