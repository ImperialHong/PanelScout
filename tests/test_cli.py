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
from panelscout.storage import ComicRepository, connect_database

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


def comic_by_source_id(comics, source_comic_id):
    for comic in comics:
        if comic.source_comic_id == source_comic_id:
            return comic
    raise AssertionError(f"Missing comic with source id {source_comic_id}")


if __name__ == "__main__":
    unittest.main()
