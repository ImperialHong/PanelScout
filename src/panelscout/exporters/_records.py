"""Shared export record helpers."""

from __future__ import annotations

from typing import Iterable

from panelscout.storage.models import Comic

EXPORT_FIELDS = (
    "id",
    "source",
    "source_comic_id",
    "title",
    "author",
    "status",
    "audience",
    "categories",
    "tags",
    "summary",
    "latest_chapter_title",
    "detail_url",
    "cover_url",
    "first_seen_at",
    "last_checked_at",
    "updated_at",
)


def comic_to_export_record(comic: Comic) -> dict[str, object]:
    """Convert a stored comic model into a serializable metadata record."""

    return {
        "id": comic.id,
        "source": comic.source,
        "source_comic_id": comic.source_comic_id,
        "title": comic.title,
        "author": comic.author,
        "status": comic.status,
        "audience": comic.audience,
        "categories": list(comic.categories),
        "tags": list(comic.tags),
        "summary": comic.summary,
        "latest_chapter_title": comic.latest_chapter_title,
        "detail_url": comic.detail_url,
        "cover_url": comic.cover_url,
        "first_seen_at": comic.first_seen_at,
        "last_checked_at": comic.last_checked_at,
        "updated_at": comic.updated_at,
    }


def comics_to_export_records(comics: Iterable[Comic]) -> list[dict[str, object]]:
    """Convert multiple comic models into export records."""

    return [comic_to_export_record(comic) for comic in comics]
