from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from panelscout.auth import (
    AuthenticatedBrowserHtmlFetcher,
    AuthSessionError,
    auth_start_url,
    default_auth_session_path,
)
from panelscout.config import PanelScoutConfig
from panelscout.crawler import FetchedHtml, RobotsDisallowedError, RobotsPolicy


class AuthSessionTests(unittest.TestCase):
    def test_default_session_path_uses_configured_session_dir(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = _test_config(root)

            path = default_auth_session_path(config, "zaimanhua")

        self.assertEqual(path, root / "sessions" / "zaimanhua.storage.json")

    def test_auth_start_url_rejects_unsupported_sources(self):
        self.assertEqual(auth_start_url("zaimanhua"), "https://manhua.zaimanhua.com")

        with self.assertRaises(ValueError):
            auth_start_url("example")

    def test_authenticated_fetcher_requires_existing_storage_state(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)

            with self.assertRaises(AuthSessionError):
                FakeAuthenticatedBrowserHtmlFetcher(
                    config=_test_config(root),
                    session_path=root / "sessions" / "missing.storage.json",
                )

    def test_authenticated_fetcher_respects_robots_before_browser_fetch(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            session_path = root / "sessions" / "zaimanhua.storage.json"
            session_path.parent.mkdir(parents=True, exist_ok=True)
            session_path.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
            robots_policy = RobotsPolicy.from_text(
                "\n".join(
                    [
                        "User-agent: *",
                        "Disallow: /blocked",
                        "Allow: /details",
                    ]
                )
            )
            fetcher = FakeAuthenticatedBrowserHtmlFetcher(
                config=_test_config(root),
                session_path=session_path,
                robots_policy=robots_policy,
            )

            fetched = fetcher.fetch_html("https://manhua.zaimanhua.com/details/15599")
            with self.assertRaises(RobotsDisallowedError):
                fetcher.fetch_html("https://manhua.zaimanhua.com/blocked")

        self.assertIn("fixture html", fetched.text)
        self.assertEqual(fetcher.urls, ["https://manhua.zaimanhua.com/details/15599"])


class FakeAuthenticatedBrowserHtmlFetcher(AuthenticatedBrowserHtmlFetcher):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.urls: list[str] = []

    def _fetch_with_playwright(self, url: str) -> FetchedHtml:
        self.urls.append(url)
        return FetchedHtml(
            url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            text="<html><body>fixture html</body></html>",
        )


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
