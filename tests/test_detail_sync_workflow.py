from pathlib import Path
import unittest

from panelscout.crawler.engine import sync_public_detail
from panelscout.crawler.fetcher import FetchedHtml
from panelscout.storage import ComicRepository, connect_database

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "zaimanhua"


class PublicDetailSyncWorkflowTests(unittest.TestCase):
    def test_sync_builds_detail_url_and_upserts_comic_without_chapters(self):
        fixture = (FIXTURE_ROOT / "details_15599.html").read_text(encoding="utf-8")
        fetcher = FakeFetcher(fixture)

        with connect_database(":memory:") as connection:
            repository = ComicRepository(connection)
            result = sync_public_detail(" 15599 ", fetcher, repository)
            stored = repository.get_comic_by_source("zaimanhua", "15599")

        self.assertEqual(fetcher.urls, ["https://manhua.zaimanhua.com/details/15599"])
        self.assertEqual(result.reference, "15599")
        self.assertEqual(result.detail_url, "https://manhua.zaimanhua.com/details/15599")
        self.assertEqual(result.comic.source_comic_id, "15599")
        self.assertEqual(result.comic.title, "伪恋同盟")
        self.assertEqual(result.chapter_count, 0)
        self.assertEqual(result.new_chapter_count, 0)
        self.assertEqual(result.chapters, ())
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.summary, result.comic.summary)

    def test_sync_accepts_public_detail_url_and_tracks_new_visible_chapters(self):
        fixture = (FIXTURE_ROOT / "details_15599_with_chapters.html").read_text(encoding="utf-8")
        fetcher = FakeFetcher(fixture)

        with connect_database(":memory:") as connection:
            repository = ComicRepository(connection)
            first = sync_public_detail(
                "https://www.zaimanhua.com/details/15599?from=test",
                fetcher,
                repository,
            )
            second = sync_public_detail("/details/15599", fetcher, repository)
            chapters = repository.list_chapters(first.comic.id or -1)

        expected_url = "https://manhua.zaimanhua.com/details/15599"
        self.assertEqual(fetcher.urls, [expected_url, expected_url])
        self.assertEqual(first.chapter_count, 2)
        self.assertEqual(first.new_chapter_count, 2)
        self.assertEqual(second.chapter_count, 2)
        self.assertEqual(second.new_chapter_count, 0)
        self.assertEqual(
            [chapter.title for chapter in chapters],
            ["第001话 背叛之后", "第002话 同盟成立"],
        )
        self.assertEqual(
            [chapter.chapter_url for chapter in chapters],
            [
                "https://manhua.zaimanhua.com/view/15599/1001.html",
                "https://manhua.zaimanhua.com/view/15599/1002.html",
            ],
        )
        self.assertEqual(
            [chapter.source_chapter_id for chapter in chapters],
            ["1001.html", "1002.html"],
        )

    def test_sync_rejects_invalid_references_before_fetching(self):
        fetcher = FakeFetcher("<html></html>")

        with connect_database(":memory:") as connection:
            repository = ComicRepository(connection)
            with self.assertRaises(ValueError):
                sync_public_detail("  ", fetcher, repository)
            with self.assertRaises(ValueError):
                sync_public_detail("https://example.test/details/15599", fetcher, repository)

        self.assertEqual(fetcher.urls, [])


class FakeFetcher:
    def __init__(self, html: str) -> None:
        self.html = html
        self.urls: list[str] = []

    def fetch_html(self, url: str) -> FetchedHtml:
        self.urls.append(url)
        return FetchedHtml(
            url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            text=self.html,
        )


if __name__ == "__main__":
    unittest.main()
