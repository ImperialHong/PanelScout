from contextlib import redirect_stdout
from io import StringIO
import csv
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from panelscout.cli import main
from panelscout.crawler.engine import (
    MetadataChange,
    PublicDetailSyncResult,
    WatchlistCheckItemResult,
    WatchlistCheckResult,
)
from panelscout.exporters import (
    export_comics_csv,
    export_comics_json,
    export_comics_markdown,
    export_watch_check_markdown,
)
from panelscout.storage import Chapter, Comic, ComicRepository, WatchlistEntry, connect_database


class ExporterTests(unittest.TestCase):
    def test_exports_json_records(self):
        comics = [_sample_comic()]

        rendered = export_comics_json(comics)
        records = json.loads(rendered)

        self.assertEqual(records[0]["title"], "Sample Comic")
        self.assertEqual(records[0]["categories"], ["action", "comedy"])
        self.assertEqual(records[0]["tags"], ["metadata"])

    def test_exports_csv_records(self):
        comics = [_sample_comic()]

        rendered = export_comics_csv(comics)
        rows = list(csv.DictReader(StringIO(rendered)))

        self.assertEqual(rows[0]["title"], "Sample Comic")
        self.assertEqual(json.loads(rows[0]["categories"]), ["action", "comedy"])
        self.assertEqual(rows[0]["author"], "Sample Author")

    def test_exports_markdown_records(self):
        comics = [_sample_comic()]

        rendered = export_comics_markdown(comics)

        self.assertIn("# PanelScout Comic Metadata", rendered)
        self.assertIn("## Sample Comic", rendered)
        self.assertIn("- Latest chapter: Chapter 3", rendered)
        self.assertIn("A metadata-only summary.", rendered)

    def test_exports_empty_markdown(self):
        rendered = export_comics_markdown([])

        self.assertIn("_No stored comics._", rendered)

    def test_exports_watch_check_markdown_report(self):
        comic = _sample_comic()
        result = WatchlistCheckResult(
            checked_count=1,
            success_count=1,
            failure_count=0,
            new_chapter_count=1,
            metadata_change_count=1,
            items=(
                WatchlistCheckItemResult(
                    entry=WatchlistEntry(
                        id=7,
                        comic=comic,
                        last_checked_at="2026-07-20T02:00:00+00:00",
                    ),
                    sync_result=PublicDetailSyncResult(
                        reference="sample-1",
                        detail_url=comic.detail_url or "",
                        comic=comic,
                        chapters=(),
                        new_chapters=(
                            Chapter(
                                comic_id=1,
                                title="Chapter 4",
                                chapter_url="https://example.test/chapter-4",
                            ),
                        ),
                        metadata_changes=(
                            MetadataChange(
                                field="latest_chapter_title",
                                previous="Chapter 3",
                                current="Chapter 4",
                            ),
                        ),
                        chapter_count=4,
                        new_chapter_count=1,
                        existing_chapter_count=3,
                    ),
                ),
            ),
        )

        rendered = export_watch_check_markdown(result)

        self.assertIn("# PanelScout Watch Check Report", rendered)
        self.assertIn("- Checked: 1", rendered)
        self.assertIn("### Sample Comic", rendered)
        self.assertIn("[Chapter 4](https://example.test/chapter-4)", rendered)
        self.assertIn("Latest chapter: Chapter 3 -> Chapter 4", rendered)

    def test_cli_export_reads_configured_temp_database(self):
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
                repository.upsert_comic(_sample_comic(source_comic_id="stored-1"))

            stdout = StringIO()
            with redirect_stdout(stdout):
                code = main(["--config", str(config_path), "export", "--format", "json"])

        self.assertEqual(code, 0)
        records = json.loads(stdout.getvalue())
        self.assertEqual(records[0]["source_comic_id"], "stored-1")

    def test_cli_export_writes_output_file(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "panel.sqlite3"
            output_path = root / "exports" / "comics.md"
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
                ComicRepository(connection).upsert_comic(_sample_comic())

            stdout = StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "--config",
                        str(config_path),
                        "export",
                        "--format",
                        "markdown",
                        "--output",
                        str(output_path),
                    ]
                )

            rendered = output_path.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("## Sample Comic", rendered)

    def test_cli_export_default_missing_database_does_not_create_home_paths(self):
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
            stdout = StringIO()
            with patch.dict(os.environ, env, clear=False):
                os.environ.pop("PANELSCOUT_CONFIG", None)
                with redirect_stdout(stdout):
                    code = main(["export", "--format", "json"])

            rendered = stdout.getvalue()

            self.assertEqual(code, 0)
            self.assertEqual(json.loads(rendered), [])
            self.assertFalse(fake_home.exists())
            self.assertFalse(fake_config_home.exists())
            self.assertFalse(fake_data_home.exists())
            self.assertFalse(fake_cache_home.exists())


def _sample_comic(*, source_comic_id: str = "sample-1") -> Comic:
    return Comic(
        id=1,
        source="zaimanhua",
        source_comic_id=source_comic_id,
        title="Sample Comic",
        author="Sample Author",
        status="ongoing",
        audience="general",
        categories=("action", "comedy"),
        tags=("metadata",),
        summary="A metadata-only summary.",
        latest_chapter_title="Chapter 3",
        detail_url="https://example.test/comic/sample-1",
        cover_url="https://example.test/cover.jpg",
        first_seen_at="2026-07-20T00:00:00+00:00",
        last_checked_at="2026-07-20T01:00:00+00:00",
        updated_at="2026-07-20T01:00:00+00:00",
    )


if __name__ == "__main__":
    unittest.main()
