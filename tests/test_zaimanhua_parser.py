from pathlib import Path
import unittest

from panelscout.adapters.zaimanhua import (
    build_detail_url,
    build_search_url,
    extract_source_comic_id,
    normalize_public_url,
)
from panelscout.parsers.zaimanhua import parse_detail_page, parse_search_results

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

    def test_url_helpers_normalize_public_urls(self):
        self.assertEqual(build_detail_url(15599), "https://manhua.zaimanhua.com/details/15599")
        self.assertEqual(build_search_url("伪恋"), "https://manhua.zaimanhua.com/dynamic/%E4%BC%AA%E6%81%8B")
        self.assertEqual(extract_source_comic_id("/details/15599"), "15599")
        self.assertEqual(
            normalize_public_url("https://www.zaimanhua.com/details/15599"),
            "https://manhua.zaimanhua.com/details/15599",
        )


if __name__ == "__main__":
    unittest.main()
