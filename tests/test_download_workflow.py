from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from panelscout.crawler import search_public_comics, sync_public_detail
from panelscout.downloader import (
    FetchedImage,
    plan_public_chapter_download,
    save_public_chapter_download,
)
from panelscout.storage import ComicRepository, connect_database

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "zaimanhua"


class DownloadWorkflowTests(unittest.TestCase):
    def test_plans_public_chapter_download_without_writing_files(self):
        fixture = (FIXTURE_ROOT / "chapter_15599_1001.html").read_text(encoding="utf-8")
        chapter_fetcher = FakeHtmlFetcher({"https://manhua.zaimanhua.com/view/15599/1001.html": fixture})

        with TemporaryDirectory() as directory:
            root = Path(directory) / "downloads"
            comic, chapter = _comic_and_chapter()

            result = plan_public_chapter_download(
                comic=comic,
                chapter=chapter,
                chapter_fetcher=chapter_fetcher,
                download_root=root,
                permission_note="用户确认该公开章节可用于个人本地归档。",
            )

            self.assertFalse(root.exists())

        self.assertEqual(len(result.images), 4)
        self.assertEqual(result.plan.items[0].relative_path.name, "001.jpg")
        self.assertEqual(result.plan.items[3].relative_path.name, "004.webp")
        self.assertEqual(chapter_fetcher.urls, ["https://manhua.zaimanhua.com/view/15599/1001.html"])

    def test_saves_public_chapter_images_and_skips_existing_files_on_rerun(self):
        fixture = (FIXTURE_ROOT / "chapter_15599_1001.html").read_text(encoding="utf-8")
        comic, chapter = _comic_and_chapter()

        with TemporaryDirectory() as directory:
            root = Path(directory)
            first_image_fetcher = FakeImageFetcher()

            first = save_public_chapter_download(
                comic=comic,
                chapter=chapter,
                chapter_fetcher=FakeHtmlFetcher({chapter.chapter_url: fixture}),
                image_fetcher=first_image_fetcher,
                download_root=root,
                permission_note="用户确认该公开章节可用于个人本地归档。",
            )

            second_image_fetcher = FakeImageFetcher()
            second = save_public_chapter_download(
                comic=comic,
                chapter=chapter,
                chapter_fetcher=FakeHtmlFetcher({chapter.chapter_url: fixture}),
                image_fetcher=second_image_fetcher,
                download_root=root,
                permission_note="用户确认该公开章节可用于个人本地归档。",
            )

            chapter_dir = root / "伪恋同盟" / "第001话 背叛之后"
            saved_files = sorted(path.name for path in chapter_dir.iterdir())

        self.assertEqual(first.saved_count, 4)
        self.assertEqual(first.skipped_count, 0)
        self.assertEqual(first.failed_count, 0)
        self.assertEqual(first_image_fetcher.urls, [
            "https://images.zaimanhua.com/comic/15599/1001/001.jpg",
            "https://manhua.zaimanhua.com/comic/15599/1001/002.png",
            "https://images.zaimanhua.com/comic/15599/1001/003.png",
            "https://images.zaimanhua.com/comic/15599/1001/004.webp",
        ])
        self.assertEqual(saved_files, ["001.jpg", "002.png", "003.png", "004.webp"])
        self.assertEqual(second.saved_count, 0)
        self.assertEqual(second.skipped_count, 4)
        self.assertEqual(second.failed_count, 0)
        self.assertEqual(second_image_fetcher.urls, [])

    def test_failed_image_fetch_does_not_create_complete_file(self):
        fixture = (FIXTURE_ROOT / "chapter_15599_1001.html").read_text(encoding="utf-8")
        comic, chapter = _comic_and_chapter()

        with TemporaryDirectory() as directory:
            root = Path(directory)
            result = save_public_chapter_download(
                comic=comic,
                chapter=chapter,
                chapter_fetcher=FakeHtmlFetcher({chapter.chapter_url: fixture}),
                image_fetcher=FakeImageFetcher(fail_urls={"https://images.zaimanhua.com/comic/15599/1001/003.png"}),
                download_root=root,
                permission_note="用户确认该公开章节可用于个人本地归档。",
            )
            failed_target = root / "伪恋同盟" / "第001话 背叛之后" / "003.png"

        self.assertEqual(result.saved_count, 3)
        self.assertEqual(result.failed_count, 1)
        self.assertFalse(failed_target.exists())

    def test_unavailable_download_directory_returns_failed_items(self):
        fixture = (FIXTURE_ROOT / "chapter_15599_1001.html").read_text(encoding="utf-8")
        comic, chapter = _comic_and_chapter()

        with TemporaryDirectory() as directory:
            blocked_root = Path(directory) / "not-a-directory"
            blocked_root.write_text("blocks directory creation", encoding="utf-8")

            result = save_public_chapter_download(
                comic=comic,
                chapter=chapter,
                chapter_fetcher=FakeHtmlFetcher({chapter.chapter_url: fixture}),
                image_fetcher=FakeImageFetcher(),
                download_root=blocked_root,
                permission_note="用户确认该公开章节可用于个人本地归档。",
            )

        self.assertEqual(result.saved_count, 0)
        self.assertEqual(result.skipped_count, 0)
        self.assertEqual(result.failed_count, 4)
        self.assertIn("could not create chapter directory", result.items[0].error)

    def test_end_to_end_minimum_line_with_fixtures_and_fake_fetchers(self):
        search_html = (FIXTURE_ROOT / "search_weisample.html").read_text(encoding="utf-8")
        detail_html = (FIXTURE_ROOT / "details_15599_with_chapters.html").read_text(encoding="utf-8")
        chapter_html = (FIXTURE_ROOT / "chapter_15599_1001.html").read_text(encoding="utf-8")

        with TemporaryDirectory() as directory:
            root = Path(directory)
            with connect_database(root / "panel.sqlite3") as connection:
                repository = ComicRepository(connection)
                search_result = search_public_comics(
                    "伪恋",
                    FakeHtmlFetcher({
                        "https://manhua.zaimanhua.com/dynamic/%E4%BC%AA%E6%81%8B": search_html
                    }),
                    repository=repository,
                )
                sync_result = sync_public_detail(
                    "15599",
                    FakeHtmlFetcher({"https://manhua.zaimanhua.com/details/15599": detail_html}),
                    repository,
                )

                comic = sync_result.comic
                chapter = sync_result.chapters[0]
                download_result = save_public_chapter_download(
                    comic=comic,
                    chapter=chapter,
                    chapter_fetcher=FakeHtmlFetcher({chapter.chapter_url: chapter_html}),
                    image_fetcher=FakeImageFetcher(),
                    download_root=root / "downloads",
                    permission_note="用户确认该公开章节可用于个人本地归档。",
                )

            expected = root / "downloads" / "伪恋同盟" / "第001话 背叛之后"
            saved_names = sorted(path.name for path in expected.iterdir())

        self.assertEqual(search_result.persisted_count, 3)
        self.assertEqual(sync_result.new_chapter_count, 2)
        self.assertEqual(download_result.saved_count, 4)
        self.assertEqual(saved_names, [
            "001.jpg",
            "002.png",
            "003.png",
            "004.webp",
        ])


class FakeHtmlFetcher:
    def __init__(self, html_by_url: dict[str, str]) -> None:
        self.html_by_url = html_by_url
        self.urls: list[str] = []

    def fetch_html(self, url: str) -> str:
        self.urls.append(url)
        try:
            return self.html_by_url[url]
        except KeyError as error:
            raise AssertionError(f"unexpected HTML URL: {url}") from error


class FakeImageFetcher:
    def __init__(self, *, fail_urls: set[str] | None = None) -> None:
        self.fail_urls = fail_urls or set()
        self.urls: list[str] = []

    def fetch_image(self, url: str) -> FetchedImage:
        self.urls.append(url)
        if url in self.fail_urls:
            raise RuntimeError("fixture image unavailable")
        extension = Path(url.split("?", 1)[0]).suffix.lstrip(".") or "jpg"
        return FetchedImage(
            url=url,
            status_code=200,
            content_type=f"image/{extension}",
            content=f"image bytes for {url}".encode("utf-8"),
        )


def _comic_and_chapter():
    from panelscout.storage.models import Chapter, Comic

    return (
        Comic(
            id=1,
            source="zaimanhua",
            source_comic_id="15599",
            title="伪恋同盟",
        ),
        Chapter(
            id=1,
            comic_id=1,
            title="第001话 背叛之后",
            chapter_url="https://manhua.zaimanhua.com/view/15599/1001.html",
            chapter_order=1,
        ),
    )


if __name__ == "__main__":
    unittest.main()
