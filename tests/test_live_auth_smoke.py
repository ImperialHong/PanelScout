from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from panelscout.adapters.zaimanhua import PUBLIC_BASE_URL, SOURCE_NAME, build_robots_url
from panelscout.auth import AuthenticatedBrowserHtmlFetcher, BrowserLoginResult
from panelscout.auth.session import DEFAULT_AUTH_STORAGE_BACKEND
from panelscout.config import PanelScoutConfig
from panelscout.crawler import load_robots_policy, sync_public_detail
from panelscout.storage import AuthSession, ComicRepository, connect_database


ENV_PATH = Path(__file__).resolve().parents[1] / ".env.local"
USERNAME_ENV = "PANELSCOUT_TEST_USERNAME"
PASSWORD_ENV = "PANELSCOUT_TEST_PASSWORD"


class LiveAuthSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        _load_local_env_file(ENV_PATH)
        if _env_flag("PANELSCOUT_LIVE_AUTH") is False:
            self.skipTest("set PANELSCOUT_LIVE_AUTH=1 to run live auth smoke tests")
        if not os.environ.get(USERNAME_ENV) or not os.environ.get(PASSWORD_ENV):
            self.skipTest(
                f"set {USERNAME_ENV} and {PASSWORD_ENV} outside git to run live auth smoke tests"
            )

    def test_live_authenticated_detail_sync_finds_visible_chapters(self):
        source = os.environ.get("PANELSCOUT_LIVE_AUTH_SOURCE", SOURCE_NAME).strip()
        if source != SOURCE_NAME:
            self.skipTest(f"unsupported live auth source: {source}")

        source_comic_id = os.environ.get("PANELSCOUT_LIVE_AUTH_COMIC_ID", "15599").strip()
        minimum_chapters = int(os.environ.get("PANELSCOUT_LIVE_AUTH_EXPECTED_MIN_CHAPTERS", "1"))

        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = _test_config(root)
            session_path = config.session_dir / f"{source}.storage.json"

            login_result = _run_live_browser_login(
                source=source,
                start_url=PUBLIC_BASE_URL,
                session_path=session_path,
                username=os.environ[USERNAME_ENV],
                password=os.environ[PASSWORD_ENV],
            )
            self.assertEqual(login_result.source, source)
            self.assertTrue(login_result.session_path.exists())

            with connect_database(config.database_path) as connection:
                repository = ComicRepository(connection)
                repository.upsert_auth_session(
                    AuthSession(
                        source=source,
                        storage_backend=login_result.storage_backend,
                        session_path=str(login_result.session_path),
                        status=login_result.status,
                    )
                )
                fetcher = AuthenticatedBrowserHtmlFetcher(
                    config=config,
                    session_path=login_result.session_path,
                    robots_policy=load_robots_policy(
                        build_robots_url(),
                        user_agent=config.user_agent,
                    ),
                    render_wait_seconds=10,
                )
                result = sync_public_detail(source_comic_id, fetcher, repository)

            self.assertGreaterEqual(len(result.chapters), minimum_chapters)


def _load_local_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = _unquote_env_value(value.strip())


def _unquote_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _run_live_browser_login(
    *,
    source: str,
    start_url: str,
    session_path: Path,
    username: str,
    password: str,
) -> BrowserLoginResult:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    session_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
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

    if not session_path.exists():
        raise AssertionError("live auth login did not create storage state")
    return BrowserLoginResult(
        source=source,
        session_path=session_path,
        storage_backend=DEFAULT_AUTH_STORAGE_BACKEND,
    )


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
        raise AssertionError("login password input was not found") from error

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
        raise AssertionError("login username input was not found")

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
        raise AssertionError("login did not reach authenticated page state") from error


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


def _test_config(root: Path) -> PanelScoutConfig:
    return PanelScoutConfig(
        data_dir=root / "data",
        database_path=root / "panel.sqlite3",
        cache_dir=root / "cache",
        session_dir=root / "sessions",
        download_root=root / "downloads",
    )


if __name__ == "__main__":
    unittest.main()
