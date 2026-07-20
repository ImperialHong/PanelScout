from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from panelscout.config import build_config
from panelscout.crawler import FetchedHtml
from panelscout.downloader import FetchedImage
from panelscout.storage import ComicRepository, connect_database
from panelscout.ui import PanelScoutUiApi, UiApiFactories
from panelscout.ui.server import UiHttpApplication, UiServerError, serve_local_ui


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "zaimanhua"
SEARCH_URL = "https://manhua.zaimanhua.com/dynamic/%E4%BC%AA%E6%81%8B"
DETAIL_URL = "https://manhua.zaimanhua.com/details/15599"
CHAPTER_URL = "https://manhua.zaimanhua.com/view/15599/1001.html"
PERMISSION_NOTE = "用户确认该公开章节可用于个人本地归档。"


class PanelScoutUiApiTests(unittest.TestCase):
    def test_search_save_and_sync_detail_with_fixture_fetchers(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = _test_config(root)
            api = PanelScoutUiApi(
                config,
                factories=UiApiFactories(
                    search_fetcher_factory=FakeHtmlFetcherFactory(
                        {SEARCH_URL: _fixture("search_weisample.html")}
                    ),
                    sync_fetcher_factory=FakeHtmlFetcherFactory(
                        {DETAIL_URL: _fixture("details_15599_with_chapters.html")}
                    ),
                ),
            )

            search = api.search({"query": "伪恋", "save": True})
            sync = api.sync({"reference": "15599", "save": True})
            state = api.state()["state"]
            with connect_database(config.database_path) as connection:
                repository = ComicRepository(connection)
                comic = repository.get_comic_by_source("zaimanhua", "15599")
                assert comic is not None
                chapters = repository.list_chapters(comic.id or -1)

        self.assertTrue(search["ok"])
        self.assertEqual(search["persisted_count"], 3)
        self.assertEqual(search["comics"][0]["title"], "伪恋同盟")
        self.assertTrue(sync["ok"])
        self.assertEqual(sync["comic"]["source_comic_id"], "15599")
        self.assertEqual([chapter["title"] for chapter in sync["chapters"]], [
            "第001话 背叛之后",
            "第002话 同盟成立",
        ])
        self.assertEqual([chapter.title for chapter in chapters], [
            "第001话 背叛之后",
            "第002话 同盟成立",
        ])
        self.assertIn(
            "15599",
            {comic["source_comic_id"] for comic in state["comics"]},
        )

    def test_download_plan_run_and_status_with_fixture_fetchers(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = _test_config(root)
            image_factory = FakeImageFetcherFactory()
            api = PanelScoutUiApi(
                config,
                factories=UiApiFactories(
                    search_fetcher_factory=FakeHtmlFetcherFactory(
                        {SEARCH_URL: _fixture("search_weisample.html")}
                    ),
                    sync_fetcher_factory=FakeHtmlFetcherFactory(
                        {DETAIL_URL: _fixture("details_15599_with_chapters.html")}
                    ),
                    download_fetcher_factory=FakeHtmlFetcherFactory(
                        {CHAPTER_URL: _fixture("chapter_15599_1001.html")}
                    ),
                    image_fetcher_factory=image_factory,
                ),
            )
            api.search({"query": "伪恋", "save": True})
            api.sync({"reference": "15599", "save": True})
            output_root = root / "downloads"
            payload = {
                "source_comic_id": "15599",
                "chapter": "1",
                "output_root": str(output_root),
                "permission_note": PERMISSION_NOTE,
            }

            plan = api.download_plan(payload)
            self.assertFalse(output_root.exists())
            run = api.download_run(payload)
            status = api.download_status(payload)
            saved_names = sorted(
                path.name
                for path in (output_root / "伪恋同盟" / "第001话 背叛之后").iterdir()
            )

        self.assertTrue(plan["ok"])
        self.assertEqual(plan["images_discovered"], 4)
        self.assertEqual(plan["items"][0]["relative_path"], "伪恋同盟/第001话 背叛之后/001.jpg")
        self.assertTrue(run["ok"])
        self.assertEqual(run["saved_count"], 4)
        self.assertEqual(run["download_status"]["saved_count"], 4)
        self.assertEqual(status["download_status"]["state"], "complete")
        self.assertEqual(status["download_status"]["label"], "已完成")
        self.assertEqual(saved_names, ["001.jpg", "002.png", "003.png", "004.webp"])
        self.assertEqual(len(image_factory.fetcher.urls), 4)

    def test_download_status_reads_partial_files_without_fetching(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = _test_config(root)
            _seed_synced_chapter(config)
            chapter_dir = root / "downloads" / "伪恋同盟" / "第001话 背叛之后"
            chapter_dir.mkdir(parents=True)
            (chapter_dir / "001.jpg").write_bytes(b"done")
            (chapter_dir / "002.png.part").write_bytes(b"partial")
            api = PanelScoutUiApi(config)

            status = api.download_status(
                {
                    "source_comic_id": "15599",
                    "chapter": "第001话 背叛之后",
                    "output_root": str(root / "downloads"),
                }
            )

        self.assertTrue(status["ok"])
        self.assertEqual(status["download_status"]["state"], "partial")
        self.assertEqual(status["download_status"]["saved_count"], 1)
        self.assertEqual(status["download_status"]["partial_count"], 1)
        self.assertEqual(status["download_status"]["files"], ["001.jpg"])
        self.assertEqual(status["download_status"]["partials"], ["002.png.part"])

    def test_http_application_routes_without_opening_a_socket(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = _test_config(root)
            api = PanelScoutUiApi(
                config,
                factories=UiApiFactories(
                    search_fetcher_factory=FakeHtmlFetcherFactory(
                        {SEARCH_URL: _fixture("search_weisample.html")}
                    )
                ),
            )
            app = UiHttpApplication(config, api=api)

            html = app.dispatch("GET", "/")
            search = app.dispatch(
                "POST",
                "/api/search",
                json.dumps({"query": "伪恋", "save": True}).encode("utf-8"),
            )
            invalid = app.dispatch("POST", "/api/search", b"[]")

        self.assertEqual(html.status_code, 200)
        self.assertIn("搜索并保存", html.body.decode("utf-8"))
        self.assertIn("/api/download/run", html.body.decode("utf-8"))
        self.assertEqual(search.status_code, 200)
        self.assertIn("伪恋同盟", search.body.decode("utf-8"))
        self.assertEqual(invalid.status_code, 400)

    def test_serve_local_ui_rejects_non_127_host_before_binding(self):
        with TemporaryDirectory() as directory:
            config = _test_config(Path(directory))

            with self.assertRaises(UiServerError):
                serve_local_ui(config, host="localhost", port=0)


class FakeHtmlFetcherFactory:
    def __init__(self, html_by_url: dict[str, str]) -> None:
        self.fetcher = FakeHtmlFetcher(html_by_url)
        self.configs = []

    def __call__(self, config):
        self.configs.append(config)
        return self.fetcher


class FakeHtmlFetcher:
    def __init__(self, html_by_url: dict[str, str]) -> None:
        self.html_by_url = html_by_url
        self.urls: list[str] = []

    def fetch_html(self, url: str) -> FetchedHtml:
        self.urls.append(url)
        try:
            html = self.html_by_url[url]
        except KeyError as error:
            raise AssertionError(f"unexpected HTML URL: {url}") from error
        return FetchedHtml(
            url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            text=html,
        )


class FakeImageFetcherFactory:
    def __init__(self) -> None:
        self.fetcher = FakeImageFetcher()
        self.configs = []

    def __call__(self, config):
        self.configs.append(config)
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
            content=f"image bytes for {url}".encode("utf-8"),
        )


def _fixture(name: str) -> str:
    return (FIXTURE_ROOT / name).read_text(encoding="utf-8")


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


def _seed_synced_chapter(config) -> None:
    api = PanelScoutUiApi(
        config,
        factories=UiApiFactories(
            search_fetcher_factory=FakeHtmlFetcherFactory(
                {SEARCH_URL: _fixture("search_weisample.html")}
            ),
            sync_fetcher_factory=FakeHtmlFetcherFactory(
                {DETAIL_URL: _fixture("details_15599_with_chapters.html")}
            ),
        ),
    )
    api.search({"query": "伪恋", "save": True})
    api.sync({"reference": "15599", "save": True})


if __name__ == "__main__":
    unittest.main()
