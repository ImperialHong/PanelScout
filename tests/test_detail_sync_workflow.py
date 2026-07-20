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
        self.assertEqual(result.existing_chapter_count, 0)
        self.assertEqual(result.chapters, ())
        self.assertEqual(result.new_chapters, ())
        self.assertEqual(result.metadata_changes, ())
        self.assertIsNotNone(result.comic.last_checked_at)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.summary, result.comic.summary)
        self.assertIsNotNone(stored.last_checked_at)

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
        self.assertEqual(first.existing_chapter_count, 0)
        self.assertEqual(
            [chapter.title for chapter in first.new_chapters],
            ["第001话 背叛之后", "第002话 同盟成立"],
        )
        self.assertEqual(first.metadata_changes, ())
        self.assertEqual(second.chapter_count, 2)
        self.assertEqual(second.new_chapter_count, 0)
        self.assertEqual(second.existing_chapter_count, 2)
        self.assertEqual(second.new_chapters, ())
        self.assertEqual(second.metadata_changes, ())
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

    def test_sync_reports_metadata_changes_new_chapters_and_then_idempotency(self):
        initial = (FIXTURE_ROOT / "details_15599_with_chapters.html").read_text(
            encoding="utf-8"
        )
        updated = (
            FIXTURE_ROOT / "details_15599_updated_with_chapters.html"
        ).read_text(encoding="utf-8")
        fetcher = FakeSequenceFetcher([initial, updated, updated])

        with connect_database(":memory:") as connection:
            repository = ComicRepository(connection)
            first = sync_public_detail("15599", fetcher, repository)
            second = sync_public_detail("15599", fetcher, repository)
            third = sync_public_detail("15599", fetcher, repository)
            stored = repository.get_comic_by_source("zaimanhua", "15599")
            assert stored is not None
            chapters = repository.list_chapters(stored.id or -1)

        self.assertEqual(first.new_chapter_count, 2)
        self.assertEqual(first.metadata_changes, ())
        self.assertEqual(second.new_chapter_count, 1)
        self.assertEqual(second.existing_chapter_count, 2)
        self.assertEqual(
            [chapter.title for chapter in second.new_chapters],
            ["第003话 重新开始"],
        )
        self.assertEqual(
            [(change.field, change.previous, change.current) for change in second.metadata_changes],
            [
                ("title", "伪恋同盟", "伪恋同盟R"),
                ("author", "榊葵/绫乃", "榊葵/绫乃/新绘"),
                ("status", "已完结", "连载中"),
                ("latest_chapter_title", "第002话", "第003话"),
            ],
        )
        self.assertEqual(third.new_chapter_count, 0)
        self.assertEqual(third.existing_chapter_count, 3)
        self.assertEqual(third.new_chapters, ())
        self.assertEqual(third.metadata_changes, ())
        self.assertEqual(stored.title, "伪恋同盟R")
        self.assertEqual(stored.latest_chapter_title, "第003话")
        self.assertIsNotNone(stored.last_checked_at)
        self.assertEqual(
            [chapter.title for chapter in chapters],
            ["第001话 背叛之后", "第002话 同盟成立", "第003话 重新开始"],
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


class FakeSequenceFetcher:
    def __init__(self, html_pages: list[str]) -> None:
        self.html_pages = html_pages
        self.urls: list[str] = []

    def fetch_html(self, url: str) -> FetchedHtml:
        self.urls.append(url)
        if not self.html_pages:
            raise AssertionError("FakeSequenceFetcher ran out of fixture pages")
        return FetchedHtml(
            url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            text=self.html_pages.pop(0),
        )


if __name__ == "__main__":
    unittest.main()
