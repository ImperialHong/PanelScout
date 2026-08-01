from pathlib import Path
import unittest

from panelscout.adapters.zaimanhua import (
    CHAPTER_DETAIL_API_ROBOTS_ALLOW_PATH,
    DETAIL_API_ROBOTS_ALLOW_PATH,
    SEARCH_API_ROBOTS_ALLOW_PATH,
    build_chapter_detail_api_url,
    build_chapter_url,
    build_detail_api_url,
    build_detail_url,
    build_search_api_url,
    build_search_url,
    extract_reader_identifiers,
    extract_source_comic_id,
    normalize_public_url,
)
from panelscout.parsers.zaimanhua import (
    parse_detail_api_response,
    parse_detail_page,
    parse_search_api_response,
    parse_search_results,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "zaimanhua"


class ZaiManHuaParserTests(unittest.TestCase):
    def test_parse_search_results_extracts_known_public_record(self):
        html = (FIXTURE_ROOT / "search_weisample.html").read_text(encoding="utf-8")

        comics = parse_search_results(html)
        first = comics[0]

        self.assertGreaterEqual(len(comics), 3)
        self.assertEqual(first.source, "zaimanhua")
        self.assertEqual(first.source_comic_id, "15599")
        self.assertEqual(first.title, "伪恋同盟")
        self.assertEqual(first.author, "榊葵/绫乃")
        self.assertEqual(first.status, "已完结")
        self.assertEqual(first.latest_chapter_title, "第112话")
        self.assertEqual(
            first.detail_url,
            "https://manhua.zaimanhua.com/details/15599",
        )
        self.assertEqual(
            first.cover_url,
            "https://images.zaimanhua.com/webpic/1/weiliantongmeng.jpg",
        )

    def test_parse_search_api_response_extracts_frontend_records(self):
        payload = (FIXTURE_ROOT / "search_api_yuehui.json").read_text(encoding="utf-8")

        comics = parse_search_api_response(payload)
        first = comics[0]

        self.assertEqual(len(comics), 2)
        self.assertEqual(first.source, "zaimanhua")
        self.assertEqual(first.source_comic_id, "82936")
        self.assertEqual(first.title, "HIGH不起来的约会")
        self.assertEqual(first.author, "すずゆき")
        self.assertEqual(first.status, "连载中")
        self.assertEqual(first.categories, ("爱情",))
        self.assertIn("嗨不起来的约会", first.tags)
        self.assertEqual(first.latest_chapter_title, "第31话")
        self.assertEqual(
            first.detail_url,
            "https://manhua.zaimanhua.com/details/82936",
        )
        self.assertEqual(
            first.cover_url,
            "https://images.zaimanhua.com/webpic/9/73163b71ae9c4c4c92e66469095b35ae.jpg",
        )

    def test_parse_detail_page_extracts_public_seo_metadata(self):
        html = (FIXTURE_ROOT / "details_15599.html").read_text(encoding="utf-8")

        detail = parse_detail_page(html)
        comic = detail.comic

        self.assertEqual(comic.source_comic_id, "15599")
        self.assertEqual(comic.title, "伪恋同盟")
        self.assertEqual(comic.author, "榊葵/绫乃")
        self.assertEqual(comic.status, "已完结")
        self.assertEqual(comic.latest_chapter_title, "第112话")
        self.assertIn("某一天的放学后", comic.summary or "")
        self.assertIn("伪恋爱同盟", comic.tags)
        self.assertEqual(
            comic.detail_url,
            "https://manhua.zaimanhua.com/details/15599",
        )
        self.assertEqual(detail.chapters, ())

    def test_parse_detail_api_response_extracts_frontend_chapter_list(self):
        payload = (FIXTURE_ROOT / "detail_api_82936.json").read_text(encoding="utf-8")

        detail = parse_detail_api_response(
            payload,
            detail_url="https://manhua.zaimanhua.com/details/82936",
        )
        comic = detail.comic

        self.assertEqual(comic.source_comic_id, "82936")
        self.assertEqual(comic.title, "HIGH不起来的约会")
        self.assertEqual(comic.author, "长门知大")
        self.assertEqual(comic.status, "连载")
        self.assertEqual(comic.categories, ("少年",))
        self.assertIn("欢乐向", comic.tags)
        self.assertEqual(comic.latest_chapter_title, "第31话")
        self.assertEqual(len(detail.chapters), 3)
        self.assertEqual(detail.chapters[0].source_chapter_id, "191401")
        self.assertEqual(detail.chapters[0].title, "第31话")
        self.assertEqual(detail.chapters[0].chapter_order, 310)
        self.assertEqual(detail.chapters[0].published_hint, "2026-07-01")
        self.assertEqual(
            detail.chapters[0].chapter_url,
            "https://manhua.zaimanhua.com/view/HIGHbuqilaideyuehui/82936/191401",
        )

    def test_url_helpers_normalize_public_urls(self):
        self.assertEqual(build_detail_url(15599), "https://manhua.zaimanhua.com/details/15599")
        self.assertEqual(
            build_detail_api_url(82936),
            "https://manhua.zaimanhua.com/api/v1/comic2/comic/detail?channel=pc&app_name=zmh&version=1.0.0&timestamp=0&uid=0&id=82936",
        )
        self.assertEqual(DETAIL_API_ROBOTS_ALLOW_PATH, "/api/v1/comic2/comic/detail")
        self.assertEqual(
            build_search_api_url("约会"),
            "https://manhua.zaimanhua.com/app/v1/search/index?keyword=%E7%BA%A6%E4%BC%9A&source=0&page=1&size=24",
        )
        self.assertEqual(SEARCH_API_ROBOTS_ALLOW_PATH, "/app/v1/search/index")
        self.assertEqual(
            build_chapter_detail_api_url("82936", "191401"),
            "https://manhua.zaimanhua.com/api/v1/comic2/chapter/detail?channel=pc&app_name=zmh&version=1.0.0&timestamp=0&uid=0&comic_id=82936&chapter_id=191401",
        )
        self.assertEqual(
            CHAPTER_DETAIL_API_ROBOTS_ALLOW_PATH,
            "/api/v1/comic2/chapter/detail",
        )
        self.assertEqual(
            build_chapter_url("82936", "191401", comic_path="HIGHbuqilaideyuehui"),
            "https://manhua.zaimanhua.com/view/HIGHbuqilaideyuehui/82936/191401",
        )
        self.assertEqual(
            build_chapter_url("15599", "1001"),
            "https://manhua.zaimanhua.com/view/15599/1001.html",
        )
        self.assertEqual(build_search_url("伪恋"), "https://manhua.zaimanhua.com/dynamic/%E4%BC%AA%E6%81%8B")
        self.assertEqual(extract_source_comic_id("/details/15599"), "15599")
        self.assertEqual(
            extract_reader_identifiers(
                "https://manhua.zaimanhua.com/view/HIGHbuqilaideyuehui/82936/191401"
            ),
            ("82936", "191401"),
        )
        self.assertEqual(
            extract_reader_identifiers("https://manhua.zaimanhua.com/view/15599/1001.html"),
            ("15599", "1001"),
        )
        self.assertEqual(
            normalize_public_url("https://www.zaimanhua.com/details/15599"),
            "https://manhua.zaimanhua.com/details/15599",
        )


if __name__ == "__main__":
    unittest.main()
