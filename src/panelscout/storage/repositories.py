"""Repository helpers for PanelScout SQLite storage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import sqlite3
from typing import Iterable

from panelscout.storage.models import Chapter, Comic, WatchCheckSchedule, WatchlistEntry


class ComicRepository:
    """Small repository for comic and chapter metadata."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def upsert_comic(self, comic: Comic) -> Comic:
        """Insert or update comic metadata and return the stored record."""

        now = _utc_now()
        values = {
            "source": comic.source,
            "source_comic_id": comic.source_comic_id,
            "title": comic.title,
            "author": comic.author,
            "status": comic.status,
            "audience": comic.audience,
            "categories": _encode_list(comic.categories),
            "tags": _encode_list(comic.tags),
            "summary": comic.summary,
            "latest_chapter_title": comic.latest_chapter_title,
            "detail_url": comic.detail_url,
            "cover_url": comic.cover_url,
            "first_seen_at": comic.first_seen_at or now,
            "last_checked_at": comic.last_checked_at,
            "updated_at": comic.updated_at or now,
        }

        self.connection.execute(
            """
            INSERT INTO comics (
                source,
                source_comic_id,
                title,
                author,
                status,
                audience,
                categories,
                tags,
                summary,
                latest_chapter_title,
                detail_url,
                cover_url,
                first_seen_at,
                last_checked_at,
                updated_at
            )
            VALUES (
                :source,
                :source_comic_id,
                :title,
                :author,
                :status,
                :audience,
                :categories,
                :tags,
                :summary,
                :latest_chapter_title,
                :detail_url,
                :cover_url,
                :first_seen_at,
                :last_checked_at,
                :updated_at
            )
            ON CONFLICT(source, source_comic_id) DO UPDATE SET
                title = excluded.title,
                author = excluded.author,
                status = excluded.status,
                audience = excluded.audience,
                categories = excluded.categories,
                tags = excluded.tags,
                summary = excluded.summary,
                latest_chapter_title = excluded.latest_chapter_title,
                detail_url = excluded.detail_url,
                cover_url = excluded.cover_url,
                last_checked_at = excluded.last_checked_at,
                updated_at = excluded.updated_at
            """,
            values,
        )
        self.connection.commit()

        stored = self.get_comic_by_source(comic.source, comic.source_comic_id)
        if stored is None:
            raise StorageError("Comic upsert succeeded but no record could be loaded")
        return stored

    def get_comic_by_source(
        self,
        source: str,
        source_comic_id: str,
    ) -> Comic | None:
        row = self.connection.execute(
            """
            SELECT *
            FROM comics
            WHERE source = ? AND source_comic_id = ?
            """,
            (source, source_comic_id),
        ).fetchone()
        return _comic_from_row(row) if row is not None else None

    def list_comics(self, *, limit: int = 100, offset: int = 0) -> list[Comic]:
        """List stored comics ordered by newest updates first."""

        rows = self.connection.execute(
            """
            SELECT *
            FROM comics
            ORDER BY updated_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (_bounded_limit(limit), _non_negative(offset)),
        ).fetchall()
        return [_comic_from_row(row) for row in rows]

    def search_comics(self, query: str, *, limit: int = 100) -> list[Comic]:
        """Search stored comics by title, author, or source comic id."""

        pattern = f"%{query.strip()}%"
        rows = self.connection.execute(
            """
            SELECT *
            FROM comics
            WHERE title LIKE ?
               OR author LIKE ?
               OR source_comic_id LIKE ?
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (pattern, pattern, pattern, _bounded_limit(limit)),
        ).fetchall()
        return [_comic_from_row(row) for row in rows]

    def upsert_chapter(self, chapter: Chapter) -> Chapter:
        """Insert or update chapter metadata and return the stored record."""

        now = _utc_now()
        values = {
            "comic_id": chapter.comic_id,
            "source_chapter_id": chapter.source_chapter_id,
            "title": chapter.title,
            "chapter_order": chapter.chapter_order,
            "chapter_url": chapter.chapter_url,
            "published_hint": chapter.published_hint,
            "first_seen_at": chapter.first_seen_at or now,
            "last_seen_at": chapter.last_seen_at or now,
        }
        self.connection.execute(
            """
            INSERT INTO chapters (
                comic_id,
                source_chapter_id,
                title,
                chapter_order,
                chapter_url,
                published_hint,
                first_seen_at,
                last_seen_at
            )
            VALUES (
                :comic_id,
                :source_chapter_id,
                :title,
                :chapter_order,
                :chapter_url,
                :published_hint,
                :first_seen_at,
                :last_seen_at
            )
            ON CONFLICT(comic_id, chapter_url) DO UPDATE SET
                source_chapter_id = excluded.source_chapter_id,
                title = excluded.title,
                chapter_order = excluded.chapter_order,
                published_hint = excluded.published_hint,
                last_seen_at = excluded.last_seen_at
            """,
            values,
        )
        self.connection.commit()

        stored = self.get_chapter_by_url(chapter.comic_id, chapter.chapter_url)
        if stored is None:
            raise StorageError("Chapter upsert succeeded but no record could be loaded")
        return stored

    def upsert_chapters(self, chapters: Iterable[Chapter]) -> list[Chapter]:
        """Insert or update multiple chapters."""

        return [self.upsert_chapter(chapter) for chapter in chapters]

    def get_chapter_by_url(self, comic_id: int, chapter_url: str) -> Chapter | None:
        row = self.connection.execute(
            """
            SELECT *
            FROM chapters
            WHERE comic_id = ? AND chapter_url = ?
            """,
            (comic_id, chapter_url),
        ).fetchone()
        return _chapter_from_row(row) if row is not None else None

    def list_chapters(self, comic_id: int) -> list[Chapter]:
        """List chapters for a comic in source order when available."""

        rows = self.connection.execute(
            """
            SELECT *
            FROM chapters
            WHERE comic_id = ?
            ORDER BY chapter_order IS NULL, chapter_order, id
            """,
            (comic_id,),
        ).fetchall()
        return [_chapter_from_row(row) for row in rows]

    def add_watchlist_entry(
        self,
        source: str,
        source_comic_id: str,
        *,
        notes: str | None = None,
    ) -> WatchlistEntry:
        """Add an existing comic to the watchlist and return the entry."""

        comic = self.get_comic_by_source(source, source_comic_id)
        if comic is None or comic.id is None:
            raise StorageError(
                "Comic is not in the local catalog; save it before adding it to the watchlist"
            )

        self.connection.execute(
            """
            INSERT INTO watchlist_entries (comic_id, notes)
            VALUES (?, ?)
            ON CONFLICT(comic_id) DO UPDATE SET
                notes = COALESCE(excluded.notes, watchlist_entries.notes)
            """,
            (comic.id, notes),
        )
        self.connection.commit()

        entry = self.get_watchlist_entry(source, source_comic_id)
        if entry is None:
            raise StorageError("Watchlist add succeeded but no entry could be loaded")
        return entry

    def remove_watchlist_entry(self, source: str, source_comic_id: str) -> bool:
        """Remove a comic from the watchlist if present."""

        comic = self.get_comic_by_source(source, source_comic_id)
        if comic is None or comic.id is None:
            return False

        cursor = self.connection.execute(
            """
            DELETE FROM watchlist_entries
            WHERE comic_id = ?
            """,
            (comic.id,),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def get_watchlist_entry(
        self,
        source: str,
        source_comic_id: str,
    ) -> WatchlistEntry | None:
        """Load a watchlist entry by source comic identity."""

        row = self.connection.execute(
            """
            SELECT
                watchlist_entries.id AS watchlist_id,
                watchlist_entries.created_at AS watchlist_created_at,
                watchlist_entries.last_checked_at AS watchlist_last_checked_at,
                watchlist_entries.notes AS watchlist_notes,
                comics.*
            FROM watchlist_entries
            JOIN comics ON comics.id = watchlist_entries.comic_id
            WHERE comics.source = ? AND comics.source_comic_id = ?
            """,
            (source, source_comic_id),
        ).fetchone()
        return _watchlist_entry_from_row(row) if row is not None else None

    def mark_watchlist_entry_checked(
        self,
        source: str,
        source_comic_id: str,
        *,
        checked_at: str | None = None,
    ) -> WatchlistEntry | None:
        """Persist the latest local watchlist check time for a watched comic."""

        comic = self.get_comic_by_source(source, source_comic_id)
        if comic is None or comic.id is None:
            return None

        self.connection.execute(
            """
            UPDATE watchlist_entries
            SET last_checked_at = ?
            WHERE comic_id = ?
            """,
            (checked_at or _utc_now(), comic.id),
        )
        self.connection.commit()
        return self.get_watchlist_entry(source, source_comic_id)

    def list_watchlist_entries(self, *, limit: int = 100, offset: int = 0) -> list[WatchlistEntry]:
        """List watchlist entries ordered by newest additions first."""

        rows = self.connection.execute(
            """
            SELECT
                watchlist_entries.id AS watchlist_id,
                watchlist_entries.created_at AS watchlist_created_at,
                watchlist_entries.last_checked_at AS watchlist_last_checked_at,
                watchlist_entries.notes AS watchlist_notes,
                comics.*
            FROM watchlist_entries
            JOIN comics ON comics.id = watchlist_entries.comic_id
            ORDER BY watchlist_entries.created_at DESC, watchlist_entries.id DESC
            LIMIT ? OFFSET ?
            """,
            (_bounded_limit(limit), _non_negative(offset)),
        ).fetchall()
        return [_watchlist_entry_from_row(row) for row in rows]

    def set_watch_check_schedule(
        self,
        source: str,
        *,
        interval_minutes: int,
        now: str | None = None,
        enabled: bool = True,
    ) -> WatchCheckSchedule:
        """Create or update a local suggested schedule for watch checks."""

        interval = int(interval_minutes)
        if interval < 1:
            raise StorageError("Watch check interval must be at least 1 minute")

        updated_at = now or _utc_now()
        next_run_at = _add_minutes(updated_at, interval)
        self.connection.execute(
            """
            INSERT INTO watch_check_schedules (
                source,
                interval_minutes,
                enabled,
                next_run_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                interval_minutes = excluded.interval_minutes,
                enabled = excluded.enabled,
                next_run_at = excluded.next_run_at,
                updated_at = excluded.updated_at
            """,
            (source, interval, int(enabled), next_run_at, updated_at),
        )
        self.connection.commit()

        schedule = self.get_watch_check_schedule(source)
        if schedule is None:
            raise StorageError("Watch schedule set succeeded but no record could be loaded")
        return schedule

    def get_watch_check_schedule(self, source: str) -> WatchCheckSchedule | None:
        """Load a local watch check schedule by source."""

        row = self.connection.execute(
            """
            SELECT *
            FROM watch_check_schedules
            WHERE source = ?
            """,
            (source,),
        ).fetchone()
        return _watch_check_schedule_from_row(row) if row is not None else None

    def clear_watch_check_schedule(self, source: str) -> bool:
        """Remove a local watch check schedule."""

        cursor = self.connection.execute(
            """
            DELETE FROM watch_check_schedules
            WHERE source = ?
            """,
            (source,),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def list_due_watch_check_schedules(
        self,
        *,
        now: str | None = None,
        limit: int = 100,
    ) -> list[WatchCheckSchedule]:
        """List enabled watch check schedules whose next run is due."""

        due_at = now or _utc_now()
        rows = self.connection.execute(
            """
            SELECT *
            FROM watch_check_schedules
            WHERE enabled = 1 AND next_run_at <= ?
            ORDER BY next_run_at ASC, id ASC
            LIMIT ?
            """,
            (due_at, _bounded_limit(limit)),
        ).fetchall()
        return [_watch_check_schedule_from_row(row) for row in rows]

    def mark_watch_check_schedule_run(
        self,
        source: str,
        *,
        ran_at: str | None = None,
    ) -> WatchCheckSchedule | None:
        """Record one manual watch check run and move the next suggested time."""

        schedule = self.get_watch_check_schedule(source)
        if schedule is None:
            return None

        timestamp = ran_at or _utc_now()
        next_run_at = _add_minutes(timestamp, schedule.interval_minutes)
        self.connection.execute(
            """
            UPDATE watch_check_schedules
            SET last_run_at = ?,
                next_run_at = ?,
                updated_at = ?
            WHERE source = ?
            """,
            (timestamp, next_run_at, timestamp, source),
        )
        self.connection.commit()
        return self.get_watch_check_schedule(source)


class StorageError(RuntimeError):
    """Raised when storage operations produce an unexpected state."""


def _comic_from_row(row: sqlite3.Row) -> Comic:
    return Comic(
        id=row["id"],
        source=row["source"],
        source_comic_id=row["source_comic_id"],
        title=row["title"],
        author=row["author"],
        status=row["status"],
        audience=row["audience"],
        categories=tuple(_decode_list(row["categories"])),
        tags=tuple(_decode_list(row["tags"])),
        summary=row["summary"],
        latest_chapter_title=row["latest_chapter_title"],
        detail_url=row["detail_url"],
        cover_url=row["cover_url"],
        first_seen_at=row["first_seen_at"],
        last_checked_at=row["last_checked_at"],
        updated_at=row["updated_at"],
    )


def _chapter_from_row(row: sqlite3.Row) -> Chapter:
    return Chapter(
        id=row["id"],
        comic_id=row["comic_id"],
        source_chapter_id=row["source_chapter_id"],
        title=row["title"],
        chapter_order=row["chapter_order"],
        chapter_url=row["chapter_url"],
        published_hint=row["published_hint"],
        first_seen_at=row["first_seen_at"],
        last_seen_at=row["last_seen_at"],
    )


def _watchlist_entry_from_row(row: sqlite3.Row) -> WatchlistEntry:
    return WatchlistEntry(
        id=row["watchlist_id"],
        comic=_comic_from_row(row),
        created_at=row["watchlist_created_at"],
        last_checked_at=row["watchlist_last_checked_at"],
        notes=row["watchlist_notes"],
    )


def _watch_check_schedule_from_row(row: sqlite3.Row) -> WatchCheckSchedule:
    return WatchCheckSchedule(
        id=row["id"],
        source=row["source"],
        interval_minutes=row["interval_minutes"],
        enabled=bool(row["enabled"]),
        last_run_at=row["last_run_at"],
        next_run_at=row["next_run_at"],
        updated_at=row["updated_at"],
    )


def _encode_list(values: Iterable[str]) -> str:
    return json.dumps(list(values), ensure_ascii=True)


def _decode_list(value: str | None) -> list[str]:
    if not value:
        return []
    decoded = json.loads(value)
    if not isinstance(decoded, list):
        raise StorageError("Expected stored JSON list")
    return [str(item) for item in decoded]


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _add_minutes(timestamp: str, minutes: int) -> str:
    return (_parse_datetime(timestamp) + timedelta(minutes=minutes)).isoformat()


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _bounded_limit(value: int) -> int:
    return max(1, min(int(value), 500))


def _non_negative(value: int) -> int:
    return max(0, int(value))
