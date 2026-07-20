"""Dataclass records used by the SQLite storage layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class Comic:
    """Stored comic metadata.

    The record intentionally contains only metadata and traceability URLs.
    """

    source: str
    source_comic_id: str
    title: str
    id: int | None = None
    author: str | None = None
    status: str | None = None
    audience: str | None = None
    categories: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    summary: str | None = None
    latest_chapter_title: str | None = None
    detail_url: str | None = None
    cover_url: str | None = None
    first_seen_at: str | None = None
    last_checked_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True, kw_only=True)
class Chapter:
    """Stored chapter metadata for a comic."""

    comic_id: int
    title: str
    chapter_url: str
    id: int | None = None
    source_chapter_id: str | None = None
    chapter_order: int | None = None
    published_hint: str | None = None
    first_seen_at: str | None = None
    last_seen_at: str | None = None


@dataclass(frozen=True, kw_only=True)
class WatchlistEntry:
    """Stored watchlist membership joined with comic metadata."""

    comic: Comic
    id: int | None = None
    created_at: str | None = None
    last_checked_at: str | None = None
    notes: str | None = None


@dataclass(frozen=True, kw_only=True)
class WatchCheckSchedule:
    """Local suggested schedule for public watchlist checks."""

    source: str
    interval_minutes: int
    next_run_at: str
    id: int | None = None
    enabled: bool = True
    last_run_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True, kw_only=True)
class CrawlJob:
    """Stored crawl job status.

    Job execution is implemented in a later unit; this model mirrors the schema.
    """

    job_type: str
    source: str
    status: str
    id: int | None = None
    query: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, kw_only=True)
class CrawlLog:
    """Stored fetch/parse observation for future crawler runs."""

    url: str
    fetched_at: str
    id: int | None = None
    job_id: int | None = None
    status_code: int | None = None
    parser_status: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, kw_only=True)
class AuthSession:
    """Stored local session metadata, never plaintext credentials."""

    source: str
    storage_backend: str
    status: str
    id: int | None = None
    session_path: str | None = None
    created_at: str | None = None
    last_validated_at: str | None = None
    expires_hint: str | None = None
    warning_acknowledged_at: str | None = None
