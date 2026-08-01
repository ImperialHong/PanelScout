from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from panelscout.auth import (
    AuthenticatedBrowserHtmlFetcher,
    AuthSessionError,
    auth_start_url,
    default_auth_session_path,
)
from panelscout.adapters.zaimanhua import (
    CHAPTER_DETAIL_API_ROBOTS_ALLOW_PATH,
    DETAIL_API_ROBOTS_ALLOW_PATH,
    build_detail_api_url,
)
from panelscout.config import PanelScoutConfig
from panelscout.crawler import FetchedHtml, RobotsDisallowedError, RobotsPolicy
from panelscout.downloader.discovery import parse_public_chapter_images


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

    def test_authenticated_fetcher_sends_storage_state_cookies_for_json(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            session_path = root / "sessions" / "zaimanhua.storage.json"
            session_path.parent.mkdir(parents=True, exist_ok=True)
            session_path.write_text(
                """
                {
                  "cookies": [
                    {
                      "name": "zmh_session",
                      "value": "test-token",
                      "domain": ".zaimanhua.com",
                      "path": "/",
                      "secure": true,
                      "expires": -1
                    },
                    {
                      "name": "other",
                      "value": "skip",
                      "domain": "example.test",
                      "path": "/"
                    }
                  ],
                  "origins": [
                    {
                      "origin": "https://manhua.zaimanhua.com",
                      "localStorage": [
                        {
                          "name": "token",
                          "value": "eyJhbGciOiJub25lIn0.eyJ1aWQiOjkzODI0OCwic3ViIjoiaGFydWhpMjAwNSJ9."
                        }
                      ]
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )
            opener = FakeJsonOpener()
            robots_policy = RobotsPolicy.from_text(
                "\n".join(
                    [
                        "User-agent: *",
                        f"Allow: {DETAIL_API_ROBOTS_ALLOW_PATH}",
                        "Disallow: /api/",
                    ]
                )
            )
            fetcher = AuthenticatedBrowserHtmlFetcher(
                config=_test_config(root),
                session_path=session_path,
                robots_policy=robots_policy,
                json_opener=opener,
            )

            fetched = fetcher.fetch_json(build_detail_api_url(15599))

        self.assertEqual(fetched.text, '{"ok":true}')
        self.assertEqual(opener.requests[0].get_header("Cookie"), "zmh_session=test-token")
        self.assertEqual(
            opener.requests[0].get_header("Authorization"),
            "Bearer eyJhbGciOiJub25lIn0.eyJ1aWQiOjkzODI0OCwic3ViIjoiaGFydWhpMjAwNSJ9.",
        )
        self.assertEqual(opener.requests[0].get_header("Platform"), "pc")
        self.assertIn("uid=938248", opener.requests[0].full_url)
        self.assertNotIn("timestamp=0", opener.requests[0].full_url)
        self.assertEqual(
            opener.requests[0].get_header("Accept"),
            "application/json,text/json,*/*",
        )

    def test_authenticated_reader_fetch_uses_chapter_api_snapshot(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            session_path = root / "sessions" / "zaimanhua.storage.json"
            session_path.parent.mkdir(parents=True, exist_ok=True)
            session_path.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
            opener = FakeJsonOpener(
                """
                {
                  "errno": 0,
                  "errmsg": "",
                  "data": {
                    "chapterInfo": {
                      "page_url": [
                        "https://images.zaimanhua.com/h%2Fsample%2F001.jpg",
                        "https://images.zaimanhua.com/h%2Fsample%2F002.jpg"
                      ]
                    }
                  }
                }
                """
            )
            robots_policy = RobotsPolicy.from_text(
                "\n".join(
                    [
                        "User-agent: *",
                        "Allow: /view/",
                        f"Allow: {CHAPTER_DETAIL_API_ROBOTS_ALLOW_PATH}",
                        "Disallow: /api/",
                    ]
                )
            )
            fetcher = AuthenticatedBrowserHtmlFetcher(
                config=_test_config(root),
                session_path=session_path,
                robots_policy=robots_policy,
                render_image_snapshot=True,
                json_opener=opener,
            )
            reader_url = "https://manhua.zaimanhua.com/view/highbuqilaideyuehui/82936/191401"

            fetched = fetcher.fetch_html(reader_url)
            images = parse_public_chapter_images(fetched.text, chapter_url=reader_url)

        self.assertIn("/api/v1/comic2/chapter/detail", opener.requests[0].full_url)
        self.assertIn("comic_id=82936", opener.requests[0].full_url)
        self.assertIn("chapter_id=191401", opener.requests[0].full_url)
        self.assertEqual(
            [image.source_url for image in images],
            [
                "https://images.zaimanhua.com/h%2Fsample%2F001.jpg",
                "https://images.zaimanhua.com/h%2Fsample%2F002.jpg",
            ],
        )


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


class FakeJsonResponse:
    status = 200
    headers = {"Content-Type": "application/json; charset=utf-8"}

    def __init__(self, body: str = '{"ok":true}') -> None:
        self.body = body

    def read(self) -> bytes:
        return self.body.encode("utf-8")


class FakeJsonOpener:
    def __init__(self, body: str = '{"ok":true}') -> None:
        self.body = body
        self.requests = []

    def __call__(self, request, *, timeout):
        self.requests.append(request)
        return FakeJsonResponse(self.body)


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
