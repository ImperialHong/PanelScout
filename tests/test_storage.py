from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from panelscout.storage import Comic, ComicRepository, StorageError, connect_database
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
                migrations = {
                    row["version"]
                    for row in connection.execute(
                        "SELECT version FROM schema_migrations"
                    ).fetchall()
                }

        self.assertIn("comics", table_names)
        self.assertIn("chapters", table_names)
        self.assertIn("watchlist_entries", table_names)
        self.assertIn("watch_check_schedules", table_names)
        self.assertIn("crawl_jobs", table_names)
        self.assertIn("crawl_logs", table_names)
        self.assertIn("auth_sessions", table_names)
        self.assertIn(3, migrations)

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

    def test_watchlist_add_list_remove_existing_comics(self):
        with connect_database(":memory:") as connection:
            repository = ComicRepository(connection)
            first = repository.upsert_comic(
                Comic(
                    source="zaimanhua",
                    source_comic_id="watch-1",
                    title="Watched One",
                    author="Creator",
                    latest_chapter_title="Chapter 9",
                    detail_url="https://example.test/details/watch-1",
                )
            )
            repository.upsert_comic(
                Comic(
                    source="zaimanhua",
                    source_comic_id="watch-2",
                    title="Watched Two",
                )
            )

            entry = repository.add_watchlist_entry(
                "zaimanhua",
                "watch-1",
                notes="priority",
            )
            duplicate = repository.add_watchlist_entry("zaimanhua", "watch-1")
            repository.add_watchlist_entry("zaimanhua", "watch-2")
            entries = repository.list_watchlist_entries()
            removed = repository.remove_watchlist_entry("zaimanhua", "watch-1")
            missing_removed = repository.remove_watchlist_entry("zaimanhua", "watch-1")
            remaining = repository.list_watchlist_entries()

        self.assertEqual(entry.id, duplicate.id)
        self.assertEqual(entry.comic.id, first.id)
        self.assertEqual(duplicate.notes, "priority")
        self.assertEqual([item.comic.source_comic_id for item in entries], ["watch-2", "watch-1"])
        self.assertTrue(removed)
        self.assertFalse(missing_removed)
        self.assertEqual([item.comic.source_comic_id for item in remaining], ["watch-2"])

    def test_watchlist_requires_existing_local_comic(self):
        with connect_database(":memory:") as connection:
            repository = ComicRepository(connection)

            with self.assertRaises(StorageError):
                repository.add_watchlist_entry("zaimanhua", "missing")

    def test_watchlist_entry_is_deleted_when_comic_is_deleted(self):
        with connect_database(":memory:") as connection:
            repository = ComicRepository(connection)
            comic = repository.upsert_comic(
                Comic(
                    source="zaimanhua",
                    source_comic_id="cascade-1",
                    title="Cascade Comic",
                )
            )
            repository.add_watchlist_entry("zaimanhua", "cascade-1")

            self.assertEqual(len(repository.list_watchlist_entries()), 1)
            connection.execute("DELETE FROM comics WHERE id = ?", (comic.id,))
            connection.commit()
            entries = repository.list_watchlist_entries()

        self.assertEqual(entries, [])

    def test_watchlist_entry_checked_time_can_be_updated(self):
        with connect_database(":memory:") as connection:
            repository = ComicRepository(connection)
            repository.upsert_comic(
                Comic(
                    source="zaimanhua",
                    source_comic_id="checked-1",
                    title="Checked Comic",
                )
            )
            repository.add_watchlist_entry("zaimanhua", "checked-1")

            updated = repository.mark_watchlist_entry_checked(
                "zaimanhua",
                "checked-1",
                checked_at="2026-07-20T01:02:03+00:00",
            )
            missing = repository.mark_watchlist_entry_checked("zaimanhua", "missing")

        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated.last_checked_at, "2026-07-20T01:02:03+00:00")
        self.assertIsNone(missing)

    def test_watch_check_schedule_can_be_set_marked_due_and_cleared(self):
        with connect_database(":memory:") as connection:
            repository = ComicRepository(connection)

            schedule = repository.set_watch_check_schedule(
                "zaimanhua",
                interval_minutes=60,
                now="2026-07-20T01:00:00+00:00",
            )
            not_due = repository.list_due_watch_check_schedules(
                now="2026-07-20T01:30:00+00:00"
            )
            due = repository.list_due_watch_check_schedules(
                now="2026-07-20T02:00:00+00:00"
            )
            marked = repository.mark_watch_check_schedule_run(
                "zaimanhua",
                ran_at="2026-07-20T02:00:00+00:00",
            )
            removed = repository.clear_watch_check_schedule("zaimanhua")
            missing_removed = repository.clear_watch_check_schedule("zaimanhua")

        self.assertEqual(schedule.next_run_at, "2026-07-20T02:00:00+00:00")
        self.assertEqual(not_due, [])
        self.assertEqual([item.source for item in due], ["zaimanhua"])
        self.assertIsNotNone(marked)
        assert marked is not None
        self.assertEqual(marked.last_run_at, "2026-07-20T02:00:00+00:00")
        self.assertEqual(marked.next_run_at, "2026-07-20T03:00:00+00:00")
        self.assertTrue(removed)
        self.assertFalse(missing_removed)

    def test_watch_check_schedule_rejects_invalid_interval(self):
        with connect_database(":memory:") as connection:
            repository = ComicRepository(connection)
            with self.assertRaises(StorageError):
                repository.set_watch_check_schedule("zaimanhua", interval_minutes=0)


if __name__ == "__main__":
    unittest.main()
