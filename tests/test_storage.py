from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from panelscout.storage import Comic, ComicRepository, connect_database
from panelscout.storage.models import Chapter


class StorageTests(unittest.TestCase):
    def test_schema_initializes_design_tables(self):
        with TemporaryDirectory() as directory:
            database_path = Path(directory) / "panel.sqlite3"
            with connect_database(database_path) as connection:
                rows = connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                ).fetchall()
                table_names = {row["name"] for row in rows}

        self.assertIn("comics", table_names)
        self.assertIn("chapters", table_names)
        self.assertIn("crawl_jobs", table_names)
        self.assertIn("crawl_logs", table_names)
        self.assertIn("auth_sessions", table_names)

    def test_upserts_and_searches_comics(self):
        with connect_database(":memory:") as connection:
            repository = ComicRepository(connection)

            first = repository.upsert_comic(
                Comic(
                    source="zaimanhua",
                    source_comic_id="sample-1",
                    title="Sample Comic",
                    author="Initial Author",
                    categories=("action", "comedy"),
                    latest_chapter_title="Chapter 1",
                    detail_url="https://example.test/comic/sample-1",
                )
            )
            second = repository.upsert_comic(
                Comic(
                    source="zaimanhua",
                    source_comic_id="sample-1",
                    title="Sample Comic Updated",
                    author="Updated Author",
                    categories=("action",),
                    tags=("metadata",),
                    latest_chapter_title="Chapter 2",
                    detail_url="https://example.test/comic/sample-1",
                )
            )

            results = repository.search_comics("updated")

        self.assertEqual(first.id, second.id)
        self.assertEqual(second.author, "Updated Author")
        self.assertEqual(second.categories, ("action",))
        self.assertEqual(second.tags, ("metadata",))
        self.assertEqual([comic.id for comic in results], [second.id])

    def test_upserts_and_lists_chapters(self):
        with connect_database(":memory:") as connection:
            repository = ComicRepository(connection)
            comic = repository.upsert_comic(
                Comic(
                    source="zaimanhua",
                    source_comic_id="sample-2",
                    title="Chaptered Comic",
                )
            )
            self.assertIsNotNone(comic.id)

            assert comic.id is not None
            first = repository.upsert_chapter(
                Chapter(
                    comic_id=comic.id,
                    source_chapter_id="c1",
                    title="Chapter 1",
                    chapter_order=1,
                    chapter_url="https://example.test/comic/sample-2/1",
                )
            )
            second = repository.upsert_chapter(
                Chapter(
                    comic_id=comic.id,
                    source_chapter_id="c1",
                    title="Chapter 1 Revised",
                    chapter_order=1,
                    chapter_url="https://example.test/comic/sample-2/1",
                )
            )
            repository.upsert_chapter(
                Chapter(
                    comic_id=comic.id,
                    title="Chapter 2",
                    chapter_order=2,
                    chapter_url="https://example.test/comic/sample-2/2",
                )
            )
            chapters = repository.list_chapters(comic.id)

        self.assertEqual(first.id, second.id)
        self.assertEqual([chapter.title for chapter in chapters], ["Chapter 1 Revised", "Chapter 2"])

    def test_schema_accepts_crawl_and_session_metadata(self):
        with connect_database(":memory:") as connection:
            job_cursor = connection.execute(
                """
                INSERT INTO crawl_jobs(job_type, source, query, status)
                VALUES (?, ?, ?, ?)
                """,
                ("search", "zaimanhua", "sample", "queued"),
            )
            connection.execute(
                """
                INSERT INTO crawl_logs(job_id, url, status_code, fetched_at, parser_status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    job_cursor.lastrowid,
                    "https://example.test/search",
                    200,
                    "2026-07-20T00:00:00+00:00",
                    "not_parsed",
                ),
            )
            connection.execute(
                """
                INSERT INTO auth_sessions(source, storage_backend, session_path, status)
                VALUES (?, ?, ?, ?)
                """,
                ("zaimanhua", "local_file", "/tmp/session.storage.json", "unknown"),
            )
            connection.commit()

            counts = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("crawl_jobs", "crawl_logs", "auth_sessions")
            }

        self.assertEqual(counts["crawl_jobs"], 1)
        self.assertEqual(counts["crawl_logs"], 1)
        self.assertEqual(counts["auth_sessions"], 1)

    def test_chapters_require_existing_comic(self):
        with connect_database(":memory:") as connection:
            repository = ComicRepository(connection)

            with self.assertRaises(sqlite3.IntegrityError):
                repository.upsert_chapter(
                    Chapter(
                        comic_id=999,
                        title="Orphan Chapter",
                        chapter_url="https://example.test/orphan",
                    )
                )


if __name__ == "__main__":
    unittest.main()
