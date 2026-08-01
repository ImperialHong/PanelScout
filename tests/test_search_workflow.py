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

    def test_search_uses_frontend_json_api_when_available(self):
        fixture = (FIXTURE_ROOT / "search_api_yuehui.json").read_text(encoding="utf-8")
        fetcher = FakeJsonFetcher(fixture)

        result = search_public_comics("  约会  ", fetcher)

        self.assertEqual(result.query, "约会")
        self.assertEqual(
            result.url,
            "https://manhua.zaimanhua.com/dynamic/%E7%BA%A6%E4%BC%9A",
        )
        self.assertEqual(
            fetcher.json_urls,
            [
                "https://manhua.zaimanhua.com/app/v1/search/index?keyword=%E7%BA%A6%E4%BC%9A&source=0&page=1&size=24"
            ],
        )
        self.assertEqual(fetcher.html_urls, [])
        self.assertEqual(len(result.comics), 2)
        self.assertEqual(result.comics[0].source_comic_id, "82936")
        self.assertEqual(result.comics[0].title, "HIGH不起来的约会")


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


class FakeJsonFetcher:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.json_urls: list[str] = []
        self.html_urls: list[str] = []

    def fetch_json(self, url: str) -> FetchedHtml:
        self.json_urls.append(url)
        return FetchedHtml(
            url=url,
            status_code=200,
            content_type="application/json; charset=utf-8",
            text=self.payload,
        )

    def fetch_html(self, url: str) -> FetchedHtml:
        self.html_urls.append(url)
        raise AssertionError("search should use JSON when fetch_json is available")


def repository_record_by_source_id(comics, source_comic_id):
    for comic in comics:
        if comic.source_comic_id == source_comic_id:
            return comic
    raise AssertionError(f"Missing comic with source id {source_comic_id}")


if __name__ == "__main__":
    unittest.main()
