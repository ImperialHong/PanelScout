from pathlib import Path
import unittest

from panelscout.crawler.engine import search_public_comics
from panelscout.crawler.fetcher import FetchedHtml
from panelscout.storage import ComicRepository, connect_database

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "zaimanhua"


class PublicSearchWorkflowTests(unittest.TestCase):
    def test_search_builds_encoded_url_and_parses_known_records(self):
        fixture = (FIXTURE_ROOT / "search_weisample.html").read_text(encoding="utf-8")
        fetcher = FakeFetcher(fixture)

        result = search_public_comics("  伪恋  ", fetcher)

        self.assertEqual(result.query, "伪恋")
        self.assertEqual(
            result.url,
            "https://manhua.zaimanhua.com/dynamic/%E4%BC%AA%E6%81%8B",
        )
        self.assertEqual(fetcher.urls, [result.url])
        self.assertEqual(result.persisted_count, 0)
        self.assertGreaterEqual(len(result.comics), 3)

        first = result.comics[0]
        self.assertEqual(first.source_comic_id, "15599")
        self.assertEqual(first.title, "伪恋同盟")
        self.assertEqual(first.author, "榊葵/绫乃")
        self.assertEqual(first.latest_chapter_title, "第112话")

    def test_search_optionally_upserts_results_into_repository(self):
        fixture = (FIXTURE_ROOT / "search_weisample.html").read_text(encoding="utf-8")
        fetcher = FakeFetcher(fixture)

        with connect_database(":memory:") as connection:
            repository = ComicRepository(connection)
            result = search_public_comics("伪恋", fetcher, repository=repository)
            stored = repository.list_comics(limit=10)

        self.assertEqual(result.persisted_count, len(result.comics))
        self.assertGreaterEqual(result.persisted_count, 3)
        self.assertEqual(len(stored), result.persisted_count)
        self.assertTrue(all(comic.id is not None for comic in result.comics))
        self.assertEqual(
            repository_record_by_source_id(stored, "15599").latest_chapter_title,
            "第112话",
        )

    def test_search_rejects_blank_query_before_fetching(self):
        fetcher = FakeFetcher("<html></html>")

        with self.assertRaises(ValueError):
            search_public_comics("  ", fetcher)

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


def repository_record_by_source_id(comics, source_comic_id):
    for comic in comics:
        if comic.source_comic_id == source_comic_id:
            return comic
    raise AssertionError(f"Missing comic with source id {source_comic_id}")


if __name__ == "__main__":
    unittest.main()
