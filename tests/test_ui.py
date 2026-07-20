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
        for item in ("搜索", "本地库", "追更", "更新历史", "下载", "设置"):
            self.assertIn(f">{item}<", html)
        self.assertIn('id="search"', html)
        self.assertIn('id="local-library"', html)
        self.assertIn('id="watchlist"', html)
        self.assertIn('id="update-history"', html)
        self.assertIn('id="downloads"', html)
        self.assertIn('id="settings"', html)
        self.assertNotIn(">Search<", html)
        self.assertNotIn(">Local Library<", html)
        self.assertNotIn(">Watchlist<", html)
        self.assertNotIn(">Update History<", html)
        self.assertNotIn(">Downloads<", html)
        self.assertNotIn(">Settings<", html)

    def test_download_area_is_planned_and_uses_expected_folder_preview(self):
        html = build_local_ui_shell()

        self.assertIn(DOWNLOAD_LAYOUT_PREVIEW, html)
        self.assertIn("下载选中章节 - 规划中", html)
        self.assertIn("重试失败任务 - 规划中", html)
        self.assertIn("disabled", html)
        self.assertIn("下载控件规划中/已禁用", html)
        self.assertIn("未启用下载引擎", html)
        self.assertIn("规划命令", html)
        self.assertIn("下载命令", html)
        self.assertIn("panelscout download plan 15599", html)
        self.assertIn("panelscout download run 15599", html)
        self.assertIn("--output-root /downloads", html)
        self.assertNotIn("Download selected chapters - planned", html)
        self.assertNotIn("Retry failed - planned", html)
        self.assertNotIn("planned/disabled", html)

    def test_write_local_ui_shell_creates_parent_directories(self):
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "nested" / "panelscout-ui.html"

            written = write_local_ui_shell(output_path)
            html = output_path.read_text(encoding="utf-8")

        self.assertEqual(written, output_path)
        self.assertIn("<title>PanelScout 本地界面</title>", html)
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

        self.assertIn("已读取本地数据库：2 部漫画，1 个追更，当前漫画 2 个章节", state.data_status)
        self.assertIn("伪恋同盟", html)
        self.assertIn("榊葵/绫乃", html)
        self.assertIn("第003话 重新开始", html)
        self.assertIn("第001话 背叛之后", html)
        self.assertIn("本地章节", html)
        self.assertIn("章节地址", html)
        self.assertIn("https://manhua.zaimanhua.com/view/15599/1001.html", html)
        self.assertIn("本地保存的简介", html)
        self.assertIn(">备注<", html)
        self.assertIn(">priority<", html)
        self.assertIn("zaimanhua：每 120 分钟", html)
        self.assertIn("/downloads/伪恋同盟/第001话 背叛之后/001.jpg", html)
        self.assertIn(
            "panelscout download plan 15599 --chapter &#x27;第001话 背叛之后&#x27; "
            "--output-root /downloads",
            html,
        )
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

        self.assertEqual(state.data_status, "配置的数据库尚不存在。")
        self.assertIn("暂无本地漫画数据", html)
        self.assertIn("本地库暂未保存漫画。", html)
        self.assertIn("当前漫画暂无本地章节。", html)
        self.assertIn(">备注<", html)
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

        self.assertEqual(state.data_status, "配置的数据库可用，但暂无数据。")
        self.assertIn("配置的数据库可用，但暂无数据。", html)
        self.assertIn("暂无本地漫画数据", html)
        self.assertIn("本地库暂未保存漫画。", html)
        self.assertIn("尚未选择漫画", html)
        self.assertIn("当前漫画暂无本地章节。", html)
        self.assertIn("暂无追更漫画。", html)
        self.assertIn("暂无本地更新历史。", html)
        self.assertIn("暂无可选本地章节。", html)
        self.assertNotIn("伪恋同盟", html)
        self.assertNotIn("海贼同人短篇合集", html)
        self.assertNotIn("静态示例预览", html)


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
