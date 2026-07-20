from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from panelscout.config import build_config
from panelscout.downloader import FetchedImage
from panelscout.storage import ComicRepository, connect_database
from panelscout.ui import PanelScoutUiApi, UiApiFactories, UiHttpApplication
from panelscout.ui.server import UiServerError, serve_local_ui


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "zaimanhua"
PERMISSION_NOTE = "用户确认该公开章节可用于个人本地归档。"


class UiRunnerTests(unittest.TestCase):
    def test_http_app_serves_interactive_shell_and_state(self):
        with TemporaryDirectory() as directory:
            config = _test_config(Path(directory))
            app = UiHttpApplication(config)

            html = app.dispatch("GET", "/")
            state = app.dispatch("GET", "/api/state")

        self.assertEqual(html.status_code, 200)
        self.assertEqual(html.content_type, "text/html; charset=utf-8")
        body = html.body.decode("utf-8")
        self.assertIn("PanelScout 格探", body)
        self.assertIn("搜索并保存", body)
        self.assertIn("同步详情", body)
        self.assertIn("规划下载", body)
        self.assertIn("确认下载", body)
        self.assertIn("读取状态", body)
        self.assertIn("api('/api/search'", body)
        self.assertNotIn("Download selected chapters", body)
        self.assertEqual(_json(state)["ok"], True)

    def test_api_search_sync_download_plan_run_and_status(self):
        search_html = (FIXTURE_ROOT / "search_weisample.html").read_text(encoding="utf-8")
        detail_html = (FIXTURE_ROOT / "details_15599_with_chapters.html").read_text(
            encoding="utf-8"
        )
        chapter_html = (FIXTURE_ROOT / "chapter_15599_1001.html").read_text(encoding="utf-8")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = _test_config(root)
            api = PanelScoutUiApi(
                config,
                factories=UiApiFactories(
                    search_fetcher_factory=FakeHtmlFetcherFactory(search_html),
                    sync_fetcher_factory=FakeHtmlFetcherFactory(detail_html),
                    download_fetcher_factory=FakeHtmlFetcherFactory(chapter_html),
                    image_fetcher_factory=FakeImageFetcherFactory(),
                ),
            )

            search = api.search({"query": "伪恋", "save": True})
            sync = api.sync({"reference": "15599", "save": True})
            output_root = root / "downloads"
            plan = api.download_plan(
                {
                    "source_comic_id": "15599",
                    "chapter": "1",
                    "output_root": str(output_root),
                    "permission_note": PERMISSION_NOTE,
                }
            )
            run = api.download_run(
                {
                    "source_comic_id": "15599",
                    "chapter": "1",
                    "output_root": str(output_root),
                    "permission_note": PERMISSION_NOTE,
                }
            )
            status = api.download_status(
                {
                    "source_comic_id": "15599",
                    "chapter": "1",
                    "output_root": str(output_root),
                }
            )
            saved_files = sorted(
                path.name
                for path in (output_root / "伪恋同盟" / "第001话 背叛之后").iterdir()
            )
            with connect_database(config.database_path) as connection:
                stored = ComicRepository(connection).get_comic_by_source("zaimanhua", "15599")

        self.assertEqual(search["persisted_count"], 3)
        self.assertIsNotNone(stored)
        self.assertEqual(sync["new_chapter_count"], 2)
        self.assertEqual(len(sync["chapters"]), 2)
        self.assertEqual(plan["images_discovered"], 4)
        self.assertEqual(plan["items"][0]["relative_path"], "伪恋同盟/第001话 背叛之后/001.jpg")
        self.assertEqual(run["saved_count"], 4)
        self.assertEqual(run["failed_count"], 0)
        self.assertEqual(saved_files, ["001.jpg", "002.png", "003.png", "004.webp"])
        self.assertEqual(status["download_status"]["saved_count"], 4)
        self.assertEqual(status["download_status"]["state"], "complete")

    def test_http_app_returns_clear_api_errors(self):
        with TemporaryDirectory() as directory:
            config = _test_config(Path(directory))
            app = UiHttpApplication(config)

            blank_search = app.dispatch("POST", "/api/search", b'{"query": "  "}')
            unknown = app.dispatch(
                "POST",
                "/api/download/status",
                json.dumps(
                    {"source_comic_id": "missing", "chapter": "1"},
                    ensure_ascii=False,
                ).encode("utf-8"),
            )
            invalid_json = app.dispatch("POST", "/api/search", b"{")

        self.assertEqual(blank_search.status_code, 400)
        self.assertIn("query cannot be blank", _json(blank_search)["error"])
        self.assertEqual(unknown.status_code, 404)
        self.assertIn("local database not found", _json(unknown)["error"])
        self.assertEqual(invalid_json.status_code, 400)
        self.assertIn("invalid JSON", _json(invalid_json)["error"])

    def test_download_plan_requires_permission_note(self):
        detail_html = (FIXTURE_ROOT / "details_15599_with_chapters.html").read_text(
            encoding="utf-8"
        )
        chapter_html = (FIXTURE_ROOT / "chapter_15599_1001.html").read_text(encoding="utf-8")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = _test_config(root)
            api = PanelScoutUiApi(
                config,
                factories=UiApiFactories(
                    sync_fetcher_factory=FakeHtmlFetcherFactory(detail_html),
                    download_fetcher_factory=FakeHtmlFetcherFactory(chapter_html),
                ),
            )
            api.sync({"reference": "15599", "save": True})

            with self.assertRaisesRegex(ValueError, "permission_note"):
                api.download_plan(
                    {
                        "source_comic_id": "15599",
                        "chapter": "1",
                        "output_root": str(root / "downloads"),
                        "permission_note": " ",
                    }
                )

    def test_serve_local_ui_rejects_public_host_before_binding(self):
        with TemporaryDirectory() as directory:
            config = _test_config(Path(directory))

            with self.assertRaisesRegex(UiServerError, "127.0.0.1"):
                serve_local_ui(config, host="0.0.0.0", port=0)


class FakeHtmlFetcherFactory:
    def __init__(self, html: str) -> None:
        self.html = html
        self.fetcher = FakeHtmlFetcher(html)

    def __call__(self, config):
        return self.fetcher


class FakeHtmlFetcher:
    def __init__(self, html: str) -> None:
        self.html = html
        self.urls: list[str] = []

    def fetch_html(self, url: str) -> str:
        self.urls.append(url)
        return self.html


class FakeImageFetcherFactory:
    def __init__(self) -> None:
        self.fetcher = FakeImageFetcher()

    def __call__(self, config):
        return self.fetcher


class FakeImageFetcher:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def fetch_image(self, url: str) -> FetchedImage:
        self.urls.append(url)
        extension = Path(url.split("?", 1)[0]).suffix.lstrip(".") or "jpg"
        return FetchedImage(
            url=url,
            status_code=200,
            content_type=f"image/{extension}",
            content=f"ui runner image bytes for {url}".encode("utf-8"),
        )


def _test_config(root: Path):
    return build_config(
        {
            "paths": {
                "data_dir": root / "data",
                "database_path": root / "panel.sqlite3",
                "cache_dir": root / "cache",
                "session_dir": root / "sessions",
                "download_root": root / "downloads",
            }
        }
    )


def _json(response):
    return json.loads(response.body.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
