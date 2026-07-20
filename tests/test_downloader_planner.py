from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from panelscout.downloader import (
    DownloadImageCandidate,
    build_download_plan,
    infer_image_extension,
    safe_path_segment,
)
from panelscout.storage.models import Chapter, Comic


class DownloaderPlannerTests(unittest.TestCase):
    def test_builds_safe_local_layout_without_creating_directories(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "downloads"
            comic = Comic(
                source="zaimanhua",
                source_comic_id="15599",
                title='伪恋/同盟: "特别篇"',
            )
            chapter = Chapter(
                comic_id=1,
                title="第001话/背叛之后?",
                chapter_url="https://manhua.zaimanhua.com/view/15599/1001.html",
                chapter_order=1,
            )

            plan = build_download_plan(
                comic=comic,
                chapter=chapter,
                images=(
                    DownloadImageCandidate(
                        source_url="https://img.example.test/a/one.JPG?token=ignored",
                    ),
                    DownloadImageCandidate(
                        source_url="https://img.example.test/a/two.png",
                    ),
                ),
                download_root=root,
                permission_note="用户确认该公开章节可用于个人本地归档。",
            )

            self.assertFalse(root.exists())

        self.assertEqual(plan.permission_note, "用户确认该公开章节可用于个人本地归档。")
        self.assertEqual(plan.comic_directory.name, '伪恋_同盟_ _特别篇_')
        self.assertEqual(plan.chapter_directory.name, "第001话_背叛之后_")
        self.assertEqual(plan.items[0].target_path.name, "001.jpg")
        self.assertEqual(plan.items[1].target_path.name, "002.png")
        self.assertEqual(
            str(plan.items[0].relative_path),
            '伪恋_同盟_ _特别篇_/第001话_背叛之后_/001.jpg',
        )
        self.assertEqual(plan.items[0].temporary_path.name, "001.jpg.part")
        self.assertEqual(plan.items[0].action, "download")

    def test_detects_existing_and_partial_files_without_writing(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            chapter_dir = root / "伪恋同盟" / "第001话"
            chapter_dir.mkdir(parents=True)
            (chapter_dir / "001.jpg").write_bytes(b"already saved")
            (chapter_dir / "002.png.part").write_bytes(b"partial")

            plan = build_download_plan(
                comic=_comic(),
                chapter=_chapter(),
                images=(
                    DownloadImageCandidate(source_url="https://img.example.test/001.jpg"),
                    DownloadImageCandidate(source_url="https://img.example.test/002.png"),
                    DownloadImageCandidate(source_url="https://img.example.test/003.webp"),
                ),
                download_root=root,
                permission_note="用户确认该公开章节可用于个人本地归档。",
            )

        self.assertEqual([item.action for item in plan.items], [
            "skip_existing",
            "resume_partial",
            "download",
        ])

    def test_duplicate_page_numbers_get_stable_suffixes(self):
        with TemporaryDirectory() as directory:
            plan = build_download_plan(
                comic=_comic(),
                chapter=_chapter(),
                images=(
                    DownloadImageCandidate(
                        source_url="https://img.example.test/page-a.jpg",
                        page_number=1,
                    ),
                    DownloadImageCandidate(
                        source_url="https://img.example.test/page-b.jpg",
                        page_number=1,
                    ),
                ),
                download_root=Path(directory),
                permission_note="用户确认该公开章节可用于个人本地归档。",
            )

        self.assertEqual([item.target_path.name for item in plan.items], [
            "001.jpg",
            "001-2.jpg",
        ])

    def test_permission_note_and_page_number_are_validated(self):
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "permission note"):
                build_download_plan(
                    comic=_comic(),
                    chapter=_chapter(),
                    images=(),
                    download_root=Path(directory),
                    permission_note=" ",
                )

            with self.assertRaisesRegex(ValueError, "page numbers"):
                build_download_plan(
                    comic=_comic(),
                    chapter=_chapter(),
                    images=(
                        DownloadImageCandidate(
                            source_url="https://img.example.test/zero.jpg",
                            page_number=0,
                        ),
                    ),
                    download_root=Path(directory),
                    permission_note="用户确认该公开章节可用于个人本地归档。",
                )

    def test_extension_inference_and_safe_segments(self):
        self.assertEqual(
            infer_image_extension(
                DownloadImageCandidate(source_url="https://img.example.test/1.JPEG")
            ),
            "jpg",
        )
        self.assertEqual(
            infer_image_extension(
                DownloadImageCandidate(
                    source_url="https://img.example.test/no-extension",
                    extension=".webp",
                )
            ),
            "webp",
        )
        self.assertEqual(
            infer_image_extension(
                DownloadImageCandidate(source_url="https://img.example.test/no-extension")
            ),
            "bin",
        )
        self.assertEqual(safe_path_segment("  /:*?  ", fallback="001话"), "001话")


def _comic() -> Comic:
    return Comic(
        source="zaimanhua",
        source_comic_id="15599",
        title="伪恋同盟",
    )


def _chapter() -> Chapter:
    return Chapter(
        comic_id=1,
        title="第001话",
        chapter_url="https://manhua.zaimanhua.com/view/15599/1001.html",
        chapter_order=1,
    )


if __name__ == "__main__":
    unittest.main()
