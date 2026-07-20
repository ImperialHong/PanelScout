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
from panelscout.storage import Comic, ComicRepository, connect_database

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
