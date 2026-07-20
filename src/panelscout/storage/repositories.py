"""Repository helpers for PanelScout SQLite storage."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import sqlite3
from typing import Iterable

from panelscout.storage.models import Chapter, Comic


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


def _bounded_limit(value: int) -> int:
    return max(1, min(int(value), 500))


def _non_negative(value: int) -> int:
    return max(0, int(value))
