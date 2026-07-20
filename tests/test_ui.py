from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from panelscout.config import build_config
from panelscout.storage import Chapter, Comic, ComicRepository, connect_database
from panelscout.ui import build_local_ui_shell, build_local_ui_state, write_local_ui_shell
from panelscout.ui.shell import DOWNLOAD_LAYOUT_PREVIEW, NAV_ITEMS


class LocalUiShellTests(unittest.TestCase):
    def test_static_shell_contains_mvp4_navigation_and_sections(self):
        html = build_local_ui_shell()

        for item in NAV_ITEMS:
            self.assertIn(f">{item}<", html)
        self.assertIn('id="search"', html)
        self.assertIn('id="local-library"', html)
        self.assertIn('id="watchlist"', html)
        self.assertIn('id="update-history"', html)
        self.assertIn('id="downloads"', html)
        self.assertIn('id="settings"', html)

    def test_download_area_is_planned_and_uses_expected_folder_preview(self):
        html = build_local_ui_shell()

        self.assertIn(DOWNLOAD_LAYOUT_PREVIEW, html)
        self.assertIn("Download selected chapters - planned", html)
        self.assertIn("Retry failed - planned", html)
        self.assertIn("disabled", html)
        self.assertIn("no downloader engine is active", html)

    def test_write_local_ui_shell_creates_parent_directories(self):
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "nested" / "panelscout-ui.html"

            written = write_local_ui_shell(output_path)
            html = output_path.read_text(encoding="utf-8")

        self.assertEqual(written, output_path)
        self.assertIn("<title>PanelScout Local UI</title>", html)
        self.assertIn(DOWNLOAD_LAYOUT_PREVIEW, html)

    def test_build_local_ui_state_reads_configured_database(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            config = _test_config(root, database_path)
            with connect_database(database_path) as connection:
                repository = ComicRepository(connection)
                comic = repository.upsert_comic(
                    Comic(
                        source="zaimanhua",
                        source_comic_id="15599",
                        title="伪恋同盟",
                        author="榊葵/绫乃",
                        status="连载中",
                        latest_chapter_title="第003话 重新开始",
                        detail_url="https://manhua.zaimanhua.com/details/15599",
                        summary="本地保存的简介",
                        last_checked_at="2026-07-20T02:00:00+00:00",
                        updated_at="2026-07-20T02:00:00+00:00",
                    )
                )
                repository.upsert_comic(
                    Comic(
                        source="zaimanhua",
                        source_comic_id="404",
                        title="备用条目",
                        updated_at="2026-07-20T01:00:00+00:00",
                    )
                )
                assert comic.id is not None
                repository.upsert_chapter(
                    Chapter(
                        comic_id=comic.id,
                        source_chapter_id="1001.html",
                        title="第001话 背叛之后",
                        chapter_order=1,
                        chapter_url="https://manhua.zaimanhua.com/view/15599/1001.html",
                    )
                )
                repository.upsert_chapter(
                    Chapter(
                        comic_id=comic.id,
                        source_chapter_id="1002.html",
                        title="第002话 同盟成立",
                        chapter_order=2,
                        chapter_url="https://manhua.zaimanhua.com/view/15599/1002.html",
                    )
                )
                repository.add_watchlist_entry("zaimanhua", "15599", notes="priority")
                repository.mark_watchlist_entry_checked(
                    "zaimanhua",
                    "15599",
                    checked_at="2026-07-20T03:00:00+00:00",
                )
                repository.set_watch_check_schedule(
                    "zaimanhua",
                    interval_minutes=120,
                    now="2026-07-20T03:00:00+00:00",
                )

            state = build_local_ui_state(config)
            html = build_local_ui_shell(state)

        self.assertIn("Loaded local database: 2 comics, 1 watched, 2 chapters", state.data_status)
        self.assertIn("伪恋同盟", html)
        self.assertIn("榊葵/绫乃", html)
        self.assertIn("第003话 重新开始", html)
        self.assertIn("第001话 背叛之后", html)
        self.assertIn("Local Chapters", html)
        self.assertIn("Chapter URL", html)
        self.assertIn("https://manhua.zaimanhua.com/view/15599/1001.html", html)
        self.assertIn("本地保存的简介", html)
        self.assertIn(">Notes<", html)
        self.assertIn(">priority<", html)
        self.assertIn("zaimanhua: every 120 minutes", html)
        self.assertIn("download_root/伪恋同盟/第001话 背叛之后/001.jpg", html)
        self.assertNotIn("海贼同人短篇合集", html)

    def test_build_local_ui_state_missing_database_uses_empty_state_without_creating_dirs(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            missing_parent = root / "missing"
            database_path = missing_parent / "panel.sqlite3"
            config = _test_config(root, database_path)

            state = build_local_ui_state(config)
            html = build_local_ui_shell(state)

            self.assertFalse(missing_parent.exists())

        self.assertEqual(state.data_status, "Configured database does not exist yet.")
        self.assertIn("No local catalog data yet", html)
        self.assertIn("No comics in local library yet.", html)
        self.assertIn("No chapters for the selected comic yet.", html)
        self.assertIn(">Notes<", html)
        self.assertIn(DOWNLOAD_LAYOUT_PREVIEW, html)

    def test_build_local_ui_state_initialized_empty_database_renders_empty_states(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            config = _test_config(root, database_path)
            with connect_database(database_path):
                pass

            state = build_local_ui_state(config)
            html = build_local_ui_shell(state)

        self.assertEqual(state.data_status, "Configured database is available but empty.")
        self.assertIn("Configured database is available but empty.", html)
        self.assertIn("No local catalog data yet", html)
        self.assertIn("No comics in local library yet.", html)
        self.assertIn("No comic selected", html)
        self.assertIn("No chapters for the selected comic yet.", html)
        self.assertIn("No watched comics yet.", html)
        self.assertIn("No local update history yet.", html)
        self.assertIn("No local chapters available yet.", html)
        self.assertNotIn("伪恋同盟", html)
        self.assertNotIn("海贼同人短篇合集", html)
        self.assertNotIn("Static sample preview", html)


def _test_config(root: Path, database_path: Path):
    return build_config(
        {
            "paths": {
                "data_dir": root / "data",
                "database_path": database_path,
                "cache_dir": root / "cache",
                "session_dir": root / "sessions",
            }
        }
    )


if __name__ == "__main__":
    unittest.main()
