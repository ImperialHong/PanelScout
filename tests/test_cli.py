from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from panelscout import __version__
from panelscout.cli import main
from panelscout.crawler import FetchedHtml, RobotsLoadError
from panelscout.downloader import FetchedImage
from panelscout.storage import Chapter, Comic, ComicRepository, connect_database

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "zaimanhua"


def run_cli(args, **kwargs):
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(args, **kwargs)
    return code, stdout.getvalue(), stderr.getvalue()


class CliTests(unittest.TestCase):
    def test_version_flag(self):
        code, stdout, stderr = run_cli(["--version"])

        self.assertEqual(code, 0)
        self.assertIn(__version__, stdout)
        self.assertEqual(stderr, "")

    def test_config_show_json_uses_config_file(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[paths]",
                        f'data_dir = "{root / "data"}"',
                        "[network]",
                        "request_delay_seconds = 1.25",
                    ]
                ),
                encoding="utf-8",
            )

            code, stdout, stderr = run_cli(
                ["--config", str(config_path), "config", "show", "--json"]
            )

        self.assertEqual(code, 0)
        self.assertIn('"request_delay_seconds": 1.25', stdout)
        self.assertIn('"metadata_only": true', stdout)
        self.assertEqual(stderr, "")

    def test_config_defaults_to_show(self):
        code, stdout, stderr = run_cli(["config"])

        self.assertEqual(code, 0)
        self.assertIn("metadata_only=True", stdout)
        self.assertEqual(stderr, "")

    def test_search_prints_results_without_saving_or_creating_default_db(self):
        fixture = (FIXTURE_ROOT / "search_weisample.html").read_text(encoding="utf-8")
        factory = FakeSearchFetcherFactory(fixture)

        with TemporaryDirectory() as directory:
            root = Path(directory)
            fake_home = root / "home"
            fake_config_home = root / "config-home"
            fake_data_home = root / "data-home"
            fake_cache_home = root / "cache-home"
            env = {
                "HOME": str(fake_home),
                "XDG_CONFIG_HOME": str(fake_config_home),
                "XDG_DATA_HOME": str(fake_data_home),
                "XDG_CACHE_HOME": str(fake_cache_home),
            }
            with patch.dict(os.environ, env, clear=False):
                os.environ.pop("PANELSCOUT_CONFIG", None)
                code, stdout, stderr = run_cli(
                    ["search", "伪恋"],
                    search_fetcher_factory=factory,
                )

        self.assertEqual(code, 0)
        self.assertIn("伪恋同盟", stdout)
        self.assertIn("榊葵/绫乃", stdout)
        self.assertIn("第112话", stdout)
        self.assertEqual(stderr, "")
        self.assertEqual(
            factory.fetcher.urls,
            ["https://manhua.zaimanhua.com/dynamic/%E4%BC%AA%E6%81%8B"],
        )
        self.assertFalse(fake_home.exists())
        self.assertFalse(fake_config_home.exists())
        self.assertFalse(fake_data_home.exists())
        self.assertFalse(fake_cache_home.exists())

    def test_search_save_persists_to_configured_temp_database(self):
        fixture = (FIXTURE_ROOT / "search_weisample.html").read_text(encoding="utf-8")
        factory = FakeSearchFetcherFactory(fixture)

        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            config_path = root / "config.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[paths]",
                        f'database_path = "{database_path}"',
                        f'data_dir = "{root / "data"}"',
                        f'cache_dir = "{root / "cache"}"',
                        f'session_dir = "{root / "sessions"}"',
                    ]
                ),
                encoding="utf-8",
            )

            code, stdout, stderr = run_cli(
                ["--config", str(config_path), "search", "伪恋", "--save"],
                search_fetcher_factory=factory,
            )
            with connect_database(database_path) as connection:
                stored = ComicRepository(connection).search_comics("伪恋")

        self.assertEqual(code, 0)
        self.assertIn("Saved: 3", stdout)
        self.assertEqual(stderr, "")
        known = comic_by_source_id(stored, "15599")
        self.assertEqual(known.title, "伪恋同盟")
        self.assertEqual(known.latest_chapter_title, "第112话")

    def test_search_blank_query_exits_before_fetching(self):
        factory = RaisingSearchFetcherFactory(AssertionError("factory should not be called"))

        code, stdout, stderr = run_cli(
            ["search", "  "],
            search_fetcher_factory=factory,
        )

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("search query cannot be blank", stderr)
        self.assertEqual(factory.calls, 0)

    def test_search_robots_load_failure_fails_closed(self):
        factory = RaisingSearchFetcherFactory(RobotsLoadError("fixture unavailable"))

        code, stdout, stderr = run_cli(
            ["search", "伪恋"],
            search_fetcher_factory=factory,
        )

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("robots policy unavailable", stderr)
        self.assertIn("fixture unavailable", stderr)

    def test_sync_prints_detail_without_saving_or_creating_default_db(self):
        fixture = (FIXTURE_ROOT / "details_15599_with_chapters.html").read_text(
            encoding="utf-8"
        )
        factory = FakeSyncFetcherFactory(fixture)

        with TemporaryDirectory() as directory:
            root = Path(directory)
            fake_home = root / "home"
            fake_config_home = root / "config-home"
            fake_data_home = root / "data-home"
            fake_cache_home = root / "cache-home"
            env = {
                "HOME": str(fake_home),
                "XDG_CONFIG_HOME": str(fake_config_home),
                "XDG_DATA_HOME": str(fake_data_home),
                "XDG_CACHE_HOME": str(fake_cache_home),
            }
            with patch.dict(os.environ, env, clear=False):
                os.environ.pop("PANELSCOUT_CONFIG", None)
                code, stdout, stderr = run_cli(
                    ["sync", "15599"],
                    sync_fetcher_factory=factory,
                )

        self.assertEqual(code, 0)
        self.assertIn("Synced detail: 伪恋同盟", stdout)
        self.assertIn("第001话 背叛之后", stdout)
        self.assertIn("第002话 同盟成立", stdout)
        self.assertIn("Chapters: 2", stdout)
        self.assertIn("New chapters: 2", stdout)
        self.assertIn("Existing chapters: 0", stdout)
        self.assertIn("New chapter details:", stdout)
        self.assertIn("Saved: no (dry run)", stdout)
        self.assertEqual(stderr, "")
        self.assertEqual(
            factory.fetcher.urls,
            ["https://manhua.zaimanhua.com/details/15599"],
        )
        self.assertFalse(fake_home.exists())
        self.assertFalse(fake_config_home.exists())
        self.assertFalse(fake_data_home.exists())
        self.assertFalse(fake_cache_home.exists())

    def test_sync_save_persists_chapters_idempotently(self):
        fixture = (FIXTURE_ROOT / "details_15599_with_chapters.html").read_text(
            encoding="utf-8"
        )
        factory = FakeSyncFetcherFactory(fixture)

        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            config_path = root / "config.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[paths]",
                        f'database_path = "{database_path}"',
                        f'data_dir = "{root / "data"}"',
                        f'cache_dir = "{root / "cache"}"',
                        f'session_dir = "{root / "sessions"}"',
                    ]
                ),
                encoding="utf-8",
            )

            first_code, first_stdout, first_stderr = run_cli(
                ["--config", str(config_path), "sync", "/details/15599", "--save"],
                sync_fetcher_factory=factory,
            )
            second_code, second_stdout, second_stderr = run_cli(
                [
                    "--config",
                    str(config_path),
                    "sync",
                    "https://www.zaimanhua.com/details/15599",
                    "--save",
                ],
                sync_fetcher_factory=factory,
            )
            with connect_database(database_path) as connection:
                repository = ComicRepository(connection)
                comic = repository.get_comic_by_source("zaimanhua", "15599")
                assert comic is not None
                chapters = repository.list_chapters(comic.id or -1)

        self.assertEqual(first_code, 0)
        self.assertEqual(second_code, 0)
        self.assertIn("Saved: yes", first_stdout)
        self.assertIn("New chapters: 2", first_stdout)
        self.assertIn("Existing chapters: 0", first_stdout)
        self.assertIn("Saved: yes", second_stdout)
        self.assertIn("New chapters: 0", second_stdout)
        self.assertIn("Existing chapters: 2", second_stdout)
        self.assertEqual(first_stderr, "")
        self.assertEqual(second_stderr, "")
        self.assertEqual(len(chapters), 2)
        self.assertEqual(
            [chapter.title for chapter in chapters],
            ["第001话 背叛之后", "第002话 同盟成立"],
        )
        self.assertEqual(
            factory.fetcher.urls,
            [
                "https://manhua.zaimanhua.com/details/15599",
                "https://manhua.zaimanhua.com/details/15599",
            ],
        )

    def test_sync_save_prints_metadata_changes_and_new_chapter_details(self):
        initial = (FIXTURE_ROOT / "details_15599_with_chapters.html").read_text(
            encoding="utf-8"
        )
        updated = (
            FIXTURE_ROOT / "details_15599_updated_with_chapters.html"
        ).read_text(encoding="utf-8")
        factory = FakeSyncSequenceFetcherFactory([initial, updated])

        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            config_path = root / "config.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[paths]",
                        f'database_path = "{database_path}"',
                        f'data_dir = "{root / "data"}"',
                        f'cache_dir = "{root / "cache"}"',
                        f'session_dir = "{root / "sessions"}"',
                    ]
                ),
                encoding="utf-8",
            )

            first_code, first_stdout, first_stderr = run_cli(
                ["--config", str(config_path), "sync", "15599", "--save"],
                sync_fetcher_factory=factory,
            )
            second_code, second_stdout, second_stderr = run_cli(
                ["--config", str(config_path), "sync", "15599", "--save"],
                sync_fetcher_factory=factory,
            )

        self.assertEqual(first_code, 0)
        self.assertEqual(second_code, 0)
        self.assertEqual(first_stderr, "")
        self.assertEqual(second_stderr, "")
        self.assertIn("New chapters: 2", first_stdout)
        self.assertNotIn("Metadata changes:", first_stdout)
        self.assertIn("Synced detail: 伪恋同盟R", second_stdout)
        self.assertIn("New chapters: 1", second_stdout)
        self.assertIn("Existing chapters: 2", second_stdout)
        self.assertIn("Metadata changes:", second_stdout)
        self.assertIn("- Title: 伪恋同盟 -> 伪恋同盟R", second_stdout)
        self.assertIn("- Author: 榊葵/绫乃 -> 榊葵/绫乃/新绘", second_stdout)
        self.assertIn("- Status: 已完结 -> 连载中", second_stdout)
        self.assertIn("- Latest chapter: 第002话 -> 第003话", second_stdout)
        self.assertIn("New chapter details:", second_stdout)
        self.assertIn("第003话 重新开始", second_stdout)

    def test_sync_blank_and_invalid_references_exit_before_fetcher_creation(self):
        factory = RaisingSyncFetcherFactory(AssertionError("factory should not be called"))

        blank_code, blank_stdout, blank_stderr = run_cli(
            ["sync", "  "],
            sync_fetcher_factory=factory,
        )
        invalid_code, invalid_stdout, invalid_stderr = run_cli(
            ["sync", "https://example.test/details/15599"],
            sync_fetcher_factory=factory,
        )

        self.assertEqual(blank_code, 1)
        self.assertEqual(blank_stdout, "")
        self.assertIn("sync reference cannot be blank", blank_stderr)
        self.assertEqual(invalid_code, 1)
        self.assertEqual(invalid_stdout, "")
        self.assertIn("sync reference invalid", invalid_stderr)
        self.assertEqual(factory.calls, 0)

    def test_sync_robots_load_failure_fails_closed(self):
        factory = RaisingSyncFetcherFactory(RobotsLoadError("fixture unavailable"))

        code, stdout, stderr = run_cli(
            ["sync", "15599"],
            sync_fetcher_factory=factory,
        )

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("robots policy unavailable", stderr)
        self.assertIn("fixture unavailable", stderr)

    def test_watch_add_list_and_remove_uses_configured_database_only(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            config_path = root / "config.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[paths]",
                        f'database_path = "{database_path}"',
                        f'data_dir = "{root / "data"}"',
                        f'cache_dir = "{root / "cache"}"',
                        f'session_dir = "{root / "sessions"}"',
                    ]
                ),
                encoding="utf-8",
            )
            with connect_database(database_path) as connection:
                ComicRepository(connection).upsert_comic(
                    Comic(
                        source="zaimanhua",
                        source_comic_id="15599",
                        title="伪恋同盟",
                        author="榊葵/绫乃",
                        status="已完结",
                        latest_chapter_title="第112话",
                        detail_url="https://manhua.zaimanhua.com/details/15599",
                    )
                )

            add_code, add_stdout, add_stderr = run_cli(
                [
                    "--config",
                    str(config_path),
                    "watch",
                    "add",
                    "15599",
                    "--notes",
                    "read next",
                ]
            )
            list_code, list_stdout, list_stderr = run_cli(
                ["--config", str(config_path), "watch", "list"]
            )
            remove_code, remove_stdout, remove_stderr = run_cli(
                ["--config", str(config_path), "watch", "remove", "15599"]
            )
            empty_code, empty_stdout, empty_stderr = run_cli(
                ["--config", str(config_path), "watch", "list"]
            )

        self.assertEqual(add_code, 0)
        self.assertIn("Watching: 伪恋同盟", add_stdout)
        self.assertIn("Notes: read next", add_stdout)
        self.assertEqual(add_stderr, "")
        self.assertEqual(list_code, 0)
        self.assertIn("Watchlist entries: 1", list_stdout)
        self.assertIn("伪恋同盟 by 榊葵/绫乃", list_stdout)
        self.assertIn("latest: 第112话", list_stdout)
        self.assertIn("notes: read next", list_stdout)
        self.assertEqual(list_stderr, "")
        self.assertEqual(remove_code, 0)
        self.assertIn("Removed watch entry: 15599", remove_stdout)
        self.assertEqual(remove_stderr, "")
        self.assertEqual(empty_code, 0)
        self.assertIn("Watchlist entries: 0", empty_stdout)
        self.assertIn("No watched comics.", empty_stdout)
        self.assertEqual(empty_stderr, "")

    def test_watch_add_requires_existing_catalog_comic_without_fetching(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            config_path = root / "config.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[paths]",
                        f'database_path = "{database_path}"',
                        f'data_dir = "{root / "data"}"',
                        f'cache_dir = "{root / "cache"}"',
                        f'session_dir = "{root / "sessions"}"',
                    ]
                ),
                encoding="utf-8",
            )

            code, stdout, stderr = run_cli(
                ["--config", str(config_path), "watch", "add", "missing"]
            )

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("watch add failed", stderr)
        self.assertIn("local catalog", stderr)

    def test_watch_add_duplicate_is_idempotent_and_updates_notes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            config_path = root / "config.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[paths]",
                        f'database_path = "{database_path}"',
                        f'data_dir = "{root / "data"}"',
                        f'cache_dir = "{root / "cache"}"',
                        f'session_dir = "{root / "sessions"}"',
                    ]
                ),
                encoding="utf-8",
            )
            with connect_database(database_path) as connection:
                ComicRepository(connection).upsert_comic(
                    Comic(
                        source="zaimanhua",
                        source_comic_id="15599",
                        title="伪恋同盟",
                    )
                )

            first_code, first_stdout, first_stderr = run_cli(
                [
                    "--config",
                    str(config_path),
                    "watch",
                    "add",
                    "15599",
                    "--notes",
                    "first note",
                ]
            )
            second_code, second_stdout, second_stderr = run_cli(
                [
                    "--config",
                    str(config_path),
                    "watch",
                    "add",
                    "15599",
                    "--notes",
                    "second note",
                ]
            )
            with connect_database(database_path) as connection:
                entries = ComicRepository(connection).list_watchlist_entries()

        self.assertEqual(first_code, 0)
        self.assertIn("Watching: 伪恋同盟", first_stdout)
        self.assertEqual(first_stderr, "")
        self.assertEqual(second_code, 0)
        self.assertIn("Watching: 伪恋同盟", second_stdout)
        self.assertEqual(second_stderr, "")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].comic.source_comic_id, "15599")
        self.assertEqual(entries[0].notes, "second note")

    def test_watch_remove_unwatched_local_catalog_comic_returns_clear_error(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            config_path = root / "config.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[paths]",
                        f'database_path = "{database_path}"',
                        f'data_dir = "{root / "data"}"',
                        f'cache_dir = "{root / "cache"}"',
                        f'session_dir = "{root / "sessions"}"',
                    ]
                ),
                encoding="utf-8",
            )
            with connect_database(database_path) as connection:
                ComicRepository(connection).upsert_comic(
                    Comic(
                        source="zaimanhua",
                        source_comic_id="15599",
                        title="伪恋同盟",
                    )
                )

            code, stdout, stderr = run_cli(
                ["--config", str(config_path), "watch", "remove", "15599"]
            )

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("watch entry not found: 15599", stderr)

    def test_watch_blank_and_unsupported_source_are_rejected(self):
        blank_code, blank_stdout, blank_stderr = run_cli(["watch", "add", "  "])
        remove_code, remove_stdout, remove_stderr = run_cli(["watch", "remove", "  "])
        source_code, source_stdout, source_stderr = run_cli(
            ["watch", "add", "15599", "--source", "example"]
        )

        self.assertEqual(blank_code, 1)
        self.assertEqual(blank_stdout, "")
        self.assertIn("watch add source comic id cannot be blank", blank_stderr)
        self.assertEqual(remove_code, 1)
        self.assertEqual(remove_stdout, "")
        self.assertIn("watch remove source comic id cannot be blank", remove_stderr)
        self.assertEqual(source_code, 1)
        self.assertEqual(source_stdout, "")
        self.assertIn("unsupported watch source 'example'", source_stderr)

    def test_watch_check_persists_public_updates_from_configured_database(self):
        updated = (
            FIXTURE_ROOT / "details_15599_updated_with_chapters.html"
        ).read_text(encoding="utf-8")
        factory = FakeSyncUrlMapFetcherFactory(
            {
                "https://manhua.zaimanhua.com/details/15599": updated,
            }
        )

        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            config_path = root / "config.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[paths]",
                        f'database_path = "{database_path}"',
                        f'data_dir = "{root / "data"}"',
                        f'cache_dir = "{root / "cache"}"',
                        f'session_dir = "{root / "sessions"}"',
                    ]
                ),
                encoding="utf-8",
            )
            with connect_database(database_path) as connection:
                repository = ComicRepository(connection)
                comic = repository.upsert_comic(
                    Comic(
                        source="zaimanhua",
                        source_comic_id="15599",
                        title="伪恋同盟",
                        author="榊葵/绫乃",
                        status="已完结",
                        latest_chapter_title="第002话",
                        detail_url="https://manhua.zaimanhua.com/details/15599",
                    )
                )
                repository.add_watchlist_entry("zaimanhua", "15599")

            code, stdout, stderr = run_cli(
                ["--config", str(config_path), "watch", "check"],
                sync_fetcher_factory=factory,
            )
            with connect_database(database_path) as connection:
                repository = ComicRepository(connection)
                chapters = repository.list_chapters(comic.id or -1)
                entry = repository.get_watchlist_entry("zaimanhua", "15599")

        self.assertEqual(code, 0)
        self.assertIn("Watch check complete", stdout)
        self.assertIn("Checked: 1", stdout)
        self.assertIn("Succeeded: 1", stdout)
        self.assertIn("Failed: 0", stdout)
        self.assertIn("New chapters: 3", stdout)
        self.assertIn("Metadata changes: 4", stdout)
        self.assertIn("第003话 重新开始", stdout)
        self.assertEqual(stderr, "")
        self.assertEqual(
            factory.fetcher.urls,
            ["https://manhua.zaimanhua.com/details/15599"],
        )
        self.assertEqual(len(chapters), 3)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertIsNotNone(entry.last_checked_at)

    def test_watch_check_empty_list_and_limit_are_local_and_clear(self):
        factory = FakeSyncUrlMapFetcherFactory({})

        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            config_path = root / "config.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[paths]",
                        f'database_path = "{database_path}"',
                        f'data_dir = "{root / "data"}"',
                        f'cache_dir = "{root / "cache"}"',
                        f'session_dir = "{root / "sessions"}"',
                    ]
                ),
                encoding="utf-8",
            )

            code, stdout, stderr = run_cli(
                ["--config", str(config_path), "watch", "check", "--limit", "1"],
                sync_fetcher_factory=factory,
            )

        self.assertEqual(code, 0)
        self.assertIn("Checked: 0", stdout)
        self.assertIn("No watched comics to check.", stdout)
        self.assertEqual(stderr, "")
        self.assertEqual(factory.fetcher.urls, [])

    def test_watch_check_reports_item_failure_without_aborting_batch(self):
        updated = (
            FIXTURE_ROOT / "details_15599_updated_with_chapters.html"
        ).read_text(encoding="utf-8")
        factory = FakeSyncUrlMapFetcherFactory(
            {
                "https://manhua.zaimanhua.com/details/15599": updated,
            }
        )

        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            config_path = root / "config.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[paths]",
                        f'database_path = "{database_path}"',
                        f'data_dir = "{root / "data"}"',
                        f'cache_dir = "{root / "cache"}"',
                        f'session_dir = "{root / "sessions"}"',
                    ]
                ),
                encoding="utf-8",
            )
            with connect_database(database_path) as connection:
                repository = ComicRepository(connection)
                repository.upsert_comic(
                    Comic(
                        source="zaimanhua",
                        source_comic_id="15599",
                        title="伪恋同盟",
                    )
                )
                repository.upsert_comic(
                    Comic(
                        source="zaimanhua",
                        source_comic_id="404",
                        title="Broken Watch",
                    )
                )
                repository.add_watchlist_entry("zaimanhua", "15599")
                repository.add_watchlist_entry("zaimanhua", "404")

            code, stdout, stderr = run_cli(
                ["--config", str(config_path), "watch", "check"],
                sync_fetcher_factory=factory,
            )

        self.assertEqual(code, 0)
        self.assertIn("Checked: 2", stdout)
        self.assertIn("Succeeded: 1", stdout)
        self.assertIn("Failed: 1", stdout)
        self.assertIn("Broken Watch", stdout)
        self.assertIn("status: failed", stdout)
        self.assertIn("No fixture for", stdout)
        self.assertEqual(stderr, "")

    def test_watch_check_writes_markdown_report_when_requested(self):
        updated = (
            FIXTURE_ROOT / "details_15599_updated_with_chapters.html"
        ).read_text(encoding="utf-8")
        factory = FakeSyncUrlMapFetcherFactory(
            {
                "https://manhua.zaimanhua.com/details/15599": updated,
            }
        )

        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            report_path = root / "reports" / "watch-check.md"
            config_path = root / "config.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[paths]",
                        f'database_path = "{database_path}"',
                        f'data_dir = "{root / "data"}"',
                        f'cache_dir = "{root / "cache"}"',
                        f'session_dir = "{root / "sessions"}"',
                    ]
                ),
                encoding="utf-8",
            )
            with connect_database(database_path) as connection:
                repository = ComicRepository(connection)
                repository.upsert_comic(
                    Comic(
                        source="zaimanhua",
                        source_comic_id="15599",
                        title="伪恋同盟",
                        latest_chapter_title="第002话",
                    )
                )
                repository.add_watchlist_entry("zaimanhua", "15599")

            code, stdout, stderr = run_cli(
                [
                    "--config",
                    str(config_path),
                    "watch",
                    "check",
                    "--report",
                    str(report_path),
                ],
                sync_fetcher_factory=factory,
            )
            report = report_path.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertIn(f"Report: {report_path}", stdout)
        self.assertEqual(stderr, "")
        self.assertIn("# PanelScout Watch Check Report", report)
        self.assertIn("伪恋同盟R", report)
        self.assertIn("第003话 重新开始", report)
        self.assertIn("Latest chapter: 第002话 -> 第003话", report)

    def test_watch_schedule_set_show_and_clear_use_configured_database(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            config_path = root / "config.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[paths]",
                        f'database_path = "{database_path}"',
                        f'data_dir = "{root / "data"}"',
                        f'cache_dir = "{root / "cache"}"',
                        f'session_dir = "{root / "sessions"}"',
                    ]
                ),
                encoding="utf-8",
            )

            set_code, set_stdout, set_stderr = run_cli(
                [
                    "--config",
                    str(config_path),
                    "watch",
                    "schedule",
                    "set",
                    "--interval-minutes",
                    "120",
                ]
            )
            show_code, show_stdout, show_stderr = run_cli(
                ["--config", str(config_path), "watch", "schedule", "show"]
            )
            clear_code, clear_stdout, clear_stderr = run_cli(
                ["--config", str(config_path), "watch", "schedule", "clear"]
            )
            empty_code, empty_stdout, empty_stderr = run_cli(
                ["--config", str(config_path), "watch", "schedule", "show"]
            )

        self.assertEqual(set_code, 0)
        self.assertIn("Watch schedule set: zaimanhua", set_stdout)
        self.assertIn("Interval minutes: 120", set_stdout)
        self.assertEqual(set_stderr, "")
        self.assertEqual(show_code, 0)
        self.assertIn("Watch schedule: zaimanhua", show_stdout)
        self.assertIn("Interval minutes: 120", show_stdout)
        self.assertEqual(show_stderr, "")
        self.assertEqual(clear_code, 0)
        self.assertIn("Watch schedule cleared: zaimanhua", clear_stdout)
        self.assertEqual(clear_stderr, "")
        self.assertEqual(empty_code, 0)
        self.assertIn("No watch schedule configured for zaimanhua.", empty_stdout)
        self.assertEqual(empty_stderr, "")

    def test_watch_schedule_due_is_local_and_rejects_bad_input(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            config_path = root / "config.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[paths]",
                        f'database_path = "{database_path}"',
                        f'data_dir = "{root / "data"}"',
                        f'cache_dir = "{root / "cache"}"',
                        f'session_dir = "{root / "sessions"}"',
                    ]
                ),
                encoding="utf-8",
            )
            with connect_database(database_path) as connection:
                ComicRepository(connection).set_watch_check_schedule(
                    "zaimanhua",
                    interval_minutes=1,
                    now="2026-01-01T00:00:00+00:00",
                )

            due_code, due_stdout, due_stderr = run_cli(
                ["--config", str(config_path), "watch", "schedule", "due"]
            )
            invalid_interval_code, invalid_interval_stdout, invalid_interval_stderr = run_cli(
                [
                    "--config",
                    str(config_path),
                    "watch",
                    "schedule",
                    "set",
                    "--interval-minutes",
                    "0",
                ]
            )
            invalid_source_code, invalid_source_stdout, invalid_source_stderr = run_cli(
                [
                    "--config",
                    str(config_path),
                    "watch",
                    "schedule",
                    "show",
                    "--source",
                    "example",
                ]
            )

        self.assertEqual(due_code, 0)
        self.assertIn("Due watch check schedules: 1", due_stdout)
        self.assertEqual(due_stderr, "")
        self.assertEqual(invalid_interval_code, 1)
        self.assertEqual(invalid_interval_stdout, "")
        self.assertIn("interval must be at least 1 minute", invalid_interval_stderr)
        self.assertEqual(invalid_source_code, 1)
        self.assertEqual(invalid_source_stdout, "")
        self.assertIn("unsupported watch schedule source 'example'", invalid_source_stderr)

    def test_ui_build_writes_static_shell_to_requested_output(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            output_path = root / "ui" / "panelscout.html"
            fake_home = root / "home"
            fake_config_home = root / "config-home"
            fake_data_home = root / "data-home"
            fake_cache_home = root / "cache-home"
            env = {
                "HOME": str(fake_home),
                "XDG_CONFIG_HOME": str(fake_config_home),
                "XDG_DATA_HOME": str(fake_data_home),
                "XDG_CACHE_HOME": str(fake_cache_home),
            }

            with patch.dict(os.environ, env, clear=False):
                os.environ.pop("PANELSCOUT_CONFIG", None)
                code, stdout, stderr = run_cli(
                    ["ui", "build", "--output", str(output_path)]
                )
            html = output_path.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertIn(f"UI 文件已写入：{output_path}", stdout)
        self.assertIn("UI 数据：配置的数据库尚不存在。", stdout)
        self.assertIn("未启动服务、网络、登录或下载任务。", stdout)
        self.assertEqual(stderr, "")
        self.assertIn(">搜索<", html)
        self.assertIn(">本地库<", html)
        self.assertIn(">追更<", html)
        self.assertIn(">更新历史<", html)
        self.assertIn(">下载<", html)
        self.assertIn(">设置<", html)
        expected_download_root = fake_home / "Downloads"
        self.assertIn(f"{expected_download_root}/漫画名/001话/001.jpg", html)
        self.assertIn("下载选中章节 - 规划中", html)
        self.assertIn("panelscout download plan SOURCE_COMIC_ID", html)
        self.assertIn(f"--output-root {expected_download_root}", html)
        self.assertIn("disabled", html)
        self.assertIn("本地库暂未保存漫画。", html)
        self.assertNotIn("Download selected chapters - planned", html)
        self.assertNotIn("Local Library", html)
        self.assertNotIn("Watchlist", html)
        self.assertFalse(fake_home.exists())
        self.assertFalse(fake_config_home.exists())
        self.assertFalse(fake_data_home.exists())
        self.assertFalse(fake_cache_home.exists())

    def test_ui_build_renders_configured_local_database_data(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            config_path = root / "config.toml"
            output_path = root / "ui" / "panelscout.html"
            config_path.write_text(
                "\n".join(
                    [
                        "[paths]",
                        f'database_path = "{database_path}"',
                        f'data_dir = "{root / "data"}"',
                        f'cache_dir = "{root / "cache"}"',
                        f'session_dir = "{root / "sessions"}"',
                    ]
                ),
                encoding="utf-8",
            )
            with connect_database(database_path) as connection:
                repository = ComicRepository(connection)
                comic = repository.upsert_comic(
                    Comic(
                        source="zaimanhua",
                        source_comic_id="15599",
                        title="伪恋同盟",
                        author="榊葵/绫乃",
                        latest_chapter_title="第003话 重新开始",
                        detail_url="https://manhua.zaimanhua.com/details/15599",
                        updated_at="2026-07-20T02:00:00+00:00",
                    )
                )
                assert comic.id is not None
                repository.upsert_chapter(
                    Chapter(
                        comic_id=comic.id,
                        title="第001话 背叛之后",
                        chapter_order=1,
                        chapter_url="https://manhua.zaimanhua.com/view/15599/1001.html",
                    )
                )
                repository.add_watchlist_entry(
                    "zaimanhua",
                    "15599",
                    notes="read after UI pass",
                )

            code, stdout, stderr = run_cli(
                ["--config", str(config_path), "ui", "build", "--output", str(output_path)]
            )
            html = output_path.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertIn("UI 数据：已读取本地数据库：1 部漫画，1 个追更，当前漫画 1 个章节", stdout)
        self.assertIn("未启动服务、网络、登录或下载任务。", stdout)
        self.assertEqual(stderr, "")
        self.assertIn("伪恋同盟", html)
        self.assertIn("榊葵/绫乃", html)
        self.assertIn("本地章节", html)
        self.assertIn("章节地址", html)
        self.assertIn("第001话 背叛之后", html)
        self.assertIn("https://manhua.zaimanhua.com/view/15599/1001.html", html)
        self.assertIn(">备注<", html)
        self.assertIn("read after UI pass", html)
        expected_download_root = Path.home() / "Downloads"
        self.assertIn(
            f"{expected_download_root}/伪恋同盟/第001话 背叛之后/001.jpg",
            html,
        )
        self.assertIn(
            "panelscout download run 15599 --chapter &#x27;第001话 背叛之后&#x27; "
            f"--output-root {expected_download_root}",
            html,
        )
        self.assertNotIn("海贼同人短篇合集", html)

    def test_ui_build_blank_output_fails_cleanly(self):
        code, stdout, stderr = run_cli(["ui", "build", "--output", "   "])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("ui build 输出路径不能为空", stderr)

    def test_ui_serve_uses_local_runner_factory(self):
        factory = FakeUiServerFactory()

        code, stdout, stderr = run_cli(
            ["ui", "serve", "--port", "0"],
            ui_server_factory=factory,
        )

        self.assertEqual(code, 0)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(factory.calls, [("127.0.0.1", 0)])

    def test_ui_serve_rejects_public_host(self):
        public_code, public_stdout, public_stderr = run_cli(
            ["ui", "serve", "--host", "0.0.0.0", "--port", "0"]
        )
        localhost_code, localhost_stdout, localhost_stderr = run_cli(
            ["ui", "serve", "--host", "localhost", "--port", "0"]
        )

        self.assertEqual(public_code, 1)
        self.assertEqual(public_stdout, "")
        self.assertIn("ui serve 配置错误", public_stderr)
        self.assertIn("127.0.0.1", public_stderr)
        self.assertEqual(localhost_code, 1)
        self.assertEqual(localhost_stdout, "")
        self.assertIn("ui serve 配置错误", localhost_stderr)
        self.assertIn("127.0.0.1", localhost_stderr)

    def test_download_plan_prints_paths_without_writing_files(self):
        chapter_fixture = (FIXTURE_ROOT / "chapter_15599_1001.html").read_text(
            encoding="utf-8"
        )
        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            config_path = root / "config.toml"
            output_root = root / "downloads"
            _write_test_config(config_path, root, database_path)
            _seed_download_chapter(database_path)

            code, stdout, stderr = run_cli(
                [
                    "--config",
                    str(config_path),
                    "download",
                    "plan",
                    "15599",
                    "--chapter",
                    "第001话 背叛之后",
                    "--output-root",
                    str(output_root),
                    "--permission-note",
                    "用户确认该公开章节可用于个人本地归档。",
                ],
                download_fetcher_factory=FakeDownloadFetcherFactory(chapter_fixture),
            )

            self.assertFalse(output_root.exists())

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Download plan: 伪恋同盟", stdout)
        self.assertIn("Images discovered: 4", stdout)
        self.assertIn("No files were downloaded or written.", stdout)
        self.assertIn("001. download: 伪恋同盟/第001话 背叛之后/001.jpg", stdout)

    def test_download_plan_uses_default_download_root_when_omitted(self):
        chapter_fixture = (FIXTURE_ROOT / "chapter_15599_1001.html").read_text(
            encoding="utf-8"
        )
        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            config_path = root / "config.toml"
            _write_test_config(config_path, root, database_path)
            _seed_download_chapter(database_path)

            code, stdout, stderr = run_cli(
                [
                    "--config",
                    str(config_path),
                    "download",
                    "plan",
                    "15599",
                    "--chapter",
                    "第001话 背叛之后",
                    "--permission-note",
                    "用户确认该公开章节可用于个人本地归档。",
                ],
                download_fetcher_factory=FakeDownloadFetcherFactory(chapter_fixture),
            )

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        expected_download_root = Path.home() / "Downloads"
        self.assertIn(f"Download root: {expected_download_root}", stdout)
        self.assertIn(
            f"Chapter directory: {expected_download_root}/伪恋同盟/第001话 背叛之后",
            stdout,
        )

    def test_download_run_saves_explicit_chapter_images(self):
        chapter_fixture = (FIXTURE_ROOT / "chapter_15599_1001.html").read_text(
            encoding="utf-8"
        )
        image_factory = FakeImageFetcherFactory()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            config_path = root / "config.toml"
            output_root = root / "downloads"
            _write_test_config(config_path, root, database_path)
            _seed_download_chapter(database_path)

            code, stdout, stderr = run_cli(
                [
                    "--config",
                    str(config_path),
                    "download",
                    "run",
                    "15599",
                    "--chapter",
                    "1",
                    "--output-root",
                    str(output_root),
                    "--permission-note",
                    "用户确认该公开章节可用于个人本地归档。",
                ],
                download_fetcher_factory=FakeDownloadFetcherFactory(chapter_fixture),
                image_fetcher_factory=image_factory,
            )
            saved_files = sorted(
                path.name
                for path in (output_root / "伪恋同盟" / "第001话 背叛之后").iterdir()
            )

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Download complete: 伪恋同盟", stdout)
        self.assertIn("Saved: 4", stdout)
        self.assertIn("Skipped: 0", stdout)
        self.assertEqual(saved_files, ["001.jpg", "002.png", "003.png", "004.webp"])
        self.assertEqual(len(image_factory.fetcher.urls), 4)

    def test_download_missing_database_fails_without_creating_default_dirs(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            fake_home = root / "home"
            fake_config_home = root / "config-home"
            fake_data_home = root / "data-home"
            fake_cache_home = root / "cache-home"
            env = {
                "HOME": str(fake_home),
                "XDG_CONFIG_HOME": str(fake_config_home),
                "XDG_DATA_HOME": str(fake_data_home),
                "XDG_CACHE_HOME": str(fake_cache_home),
            }

            with patch.dict(os.environ, env, clear=False):
                os.environ.pop("PANELSCOUT_CONFIG", None)
                code, stdout, stderr = run_cli(
                    [
                        "download",
                        "plan",
                        "15599",
                        "--chapter",
                        "1",
                        "--output-root",
                        str(root / "downloads"),
                        "--permission-note",
                        "用户确认该公开章节可用于个人本地归档。",
                    ],
                    download_fetcher_factory=RaisingDownloadFetcherFactory(
                        AssertionError("factory should not be called")
                    ),
                )

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("local database not found", stderr)
        self.assertFalse(fake_home.exists())
        self.assertFalse(fake_config_home.exists())
        self.assertFalse(fake_data_home.exists())
        self.assertFalse(fake_cache_home.exists())


def _write_test_config(config_path: Path, root: Path, database_path: Path) -> None:
    config_path.write_text(
        "\n".join(
            [
                "[paths]",
                f'database_path = "{database_path}"',
                f'data_dir = "{root / "data"}"',
                f'cache_dir = "{root / "cache"}"',
                f'session_dir = "{root / "sessions"}"',
            ]
        ),
        encoding="utf-8",
    )


def _seed_download_chapter(database_path: Path) -> None:
    with connect_database(database_path) as connection:
        repository = ComicRepository(connection)
        comic = repository.upsert_comic(
            Comic(
                source="zaimanhua",
                source_comic_id="15599",
                title="伪恋同盟",
                author="榊葵/绫乃",
                latest_chapter_title="第001话 背叛之后",
                detail_url="https://manhua.zaimanhua.com/details/15599",
            )
        )
        assert comic.id is not None
        repository.upsert_chapter(
            Chapter(
                comic_id=comic.id,
                title="第001话 背叛之后",
                chapter_order=1,
                chapter_url="https://manhua.zaimanhua.com/view/15599/1001.html",
                source_chapter_id="1001",
            )
        )


class FakeDownloadFetcherFactory:
    def __init__(self, html: str) -> None:
        self.fetcher = FakeDownloadFetcher(html)
        self.configs = []

    def __call__(self, config):
        self.configs.append(config)
        return self.fetcher


class FakeDownloadFetcher:
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


class RaisingDownloadFetcherFactory:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    def __call__(self, config):
        self.calls += 1
        raise self.error


class FakeImageFetcherFactory:
    def __init__(self) -> None:
        self.fetcher = FakeCliImageFetcher()
        self.configs = []

    def __call__(self, config):
        self.configs.append(config)
        return self.fetcher


class FakeCliImageFetcher:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def fetch_image(self, url: str) -> FetchedImage:
        self.urls.append(url)
        extension = Path(url.split("?", 1)[0]).suffix.lstrip(".") or "jpg"
        return FetchedImage(
            url=url,
            status_code=200,
            content_type=f"image/{extension}",
            content=f"cli image bytes for {url}".encode("utf-8"),
        )


class FakeUiServerFactory:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def __call__(self, config, *, host: str, port: int) -> None:
        self.calls.append((host, port))


class FakeSearchFetcherFactory:
    def __init__(self, html: str) -> None:
        self.fetcher = FakeSearchFetcher(html)
        self.configs = []

    def __call__(self, config):
        self.configs.append(config)
        return self.fetcher


class FakeSearchFetcher:
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


class RaisingSearchFetcherFactory:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    def __call__(self, config):
        self.calls += 1
        raise self.error


class FakeSyncFetcherFactory:
    def __init__(self, html: str) -> None:
        self.fetcher = FakeSyncFetcher(html)
        self.configs = []

    def __call__(self, config):
        self.configs.append(config)
        return self.fetcher


class FakeSyncFetcher:
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


class FakeSyncSequenceFetcherFactory:
    def __init__(self, html_pages: list[str]) -> None:
        self.fetcher = FakeSyncSequenceFetcher(html_pages)
        self.configs = []

    def __call__(self, config):
        self.configs.append(config)
        return self.fetcher


class FakeSyncSequenceFetcher:
    def __init__(self, html_pages: list[str]) -> None:
        self.html_pages = html_pages
        self.urls: list[str] = []

    def fetch_html(self, url: str) -> FetchedHtml:
        self.urls.append(url)
        if not self.html_pages:
            raise AssertionError("FakeSyncSequenceFetcher ran out of fixture pages")
        return FetchedHtml(
            url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            text=self.html_pages.pop(0),
        )


class FakeSyncUrlMapFetcherFactory:
    def __init__(self, html_by_url: dict[str, str]) -> None:
        self.fetcher = FakeSyncUrlMapFetcher(html_by_url)
        self.configs = []

    def __call__(self, config):
        self.configs.append(config)
        return self.fetcher


class FakeSyncUrlMapFetcher:
    def __init__(self, html_by_url: dict[str, str]) -> None:
        self.html_by_url = html_by_url
        self.urls: list[str] = []

    def fetch_html(self, url: str) -> FetchedHtml:
        self.urls.append(url)
        html = self.html_by_url.get(url)
        if html is None:
            raise RuntimeError(f"No fixture for {url}")
        return FetchedHtml(
            url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            text=html,
        )


class RaisingSyncFetcherFactory:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    def __call__(self, config):
        self.calls += 1
        raise self.error


def comic_by_source_id(comics, source_comic_id):
    for comic in comics:
        if comic.source_comic_id == source_comic_id:
            return comic
    raise AssertionError(f"Missing comic with source id {source_comic_id}")


if __name__ == "__main__":
    unittest.main()
