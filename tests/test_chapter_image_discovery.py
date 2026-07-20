from pathlib import Path
import unittest

from panelscout.downloader import parse_public_chapter_images

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "zaimanhua"


class ChapterImageDiscoveryTests(unittest.TestCase):
    def test_parses_public_chapter_images_from_fixture(self):
        html = (FIXTURE_ROOT / "chapter_15599_1001.html").read_text(encoding="utf-8")

        images = parse_public_chapter_images(
            html,
            chapter_url="https://manhua.zaimanhua.com/view/15599/1001.html",
        )

        self.assertEqual([image.page_number for image in images], [1, 2, 3, 4])
        self.assertEqual([image.extension for image in images], ["jpg", "png", "png", "webp"])
        self.assertEqual(
            [image.source_url for image in images],
            [
                "https://images.zaimanhua.com/comic/15599/1001/001.jpg",
                "https://manhua.zaimanhua.com/comic/15599/1001/002.png",
                "https://images.zaimanhua.com/comic/15599/1001/003.png",
                "https://images.zaimanhua.com/comic/15599/1001/004.webp",
            ],
        )

    def test_ignores_non_image_markup_and_dedupes_urls(self):
        html = """
        <img src="/static/avatar.svg">
        <img data-src="/comic/1/001.jpg">
        <img data-original="/comic/1/001.jpg">
        <script>window.x = ["https://example.test/not-a-page.txt"]</script>
        """

        images = parse_public_chapter_images(
            html,
            chapter_url="https://manhua.zaimanhua.com/view/1/1.html",
        )

        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].source_url, "https://manhua.zaimanhua.com/comic/1/001.jpg")


if __name__ == "__main__":
    unittest.main()
