"""Local data view models for the static PanelScout UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from panelscout.config import PanelScoutConfig
from panelscout.storage import ComicRepository, connect_database
from panelscout.storage.models import Chapter, Comic, WatchCheckSchedule, WatchlistEntry


@dataclass(frozen=True, kw_only=True)
class UiComic:
    source: str
    source_comic_id: str
    title: str
    id: int | None = None
    author: str | None = None
    status: str | None = None
    latest_chapter_title: str | None = None
    detail_url: str | None = None
    summary: str | None = None
    last_checked_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True, kw_only=True)
class UiChapter:
    title: str
    chapter_url: str
    chapter_order: int | None = None


@dataclass(frozen=True, kw_only=True)
class UiWatchlistEntry:
    comic: UiComic
    created_at: str | None = None
    last_checked_at: str | None = None
    notes: str | None = None


@dataclass(frozen=True, kw_only=True)
class UiWatchSchedule:
    source: str
    interval_minutes: int
    next_run_at: str
    enabled: bool
    last_run_at: str | None = None


@dataclass(frozen=True, kw_only=True)
class UiHistoryRow:
    kind: str
    comic_title: str
    detail: str


@dataclass(frozen=True, kw_only=True)
class LocalUiState:
    database_path: str
    source: str
    data_status: str
    comics: tuple[UiComic, ...] = ()
    selected_comic: UiComic | None = None
    chapters: tuple[UiChapter, ...] = ()
    watchlist_entries: tuple[UiWatchlistEntry, ...] = ()
    watch_schedule: UiWatchSchedule | None = None
    history_rows: tuple[UiHistoryRow, ...] = ()


def build_local_ui_state(config: PanelScoutConfig) -> LocalUiState:
    """Build a UI state snapshot from the configured local database if it exists."""

    database_path = config.database_path
    database_display = str(database_path)

    if str(database_path) != ":memory:":
        expanded_path = Path(database_path).expanduser()
        if not expanded_path.exists():
            return LocalUiState(
                database_path=database_display,
                source=config.source,
                data_status="Configured database does not exist yet.",
            )

    try:
        with connect_database(database_path, initialize=False) as connection:
            repository = ComicRepository(connection)
            comics = tuple(_comic_view(comic) for comic in repository.list_comics(limit=50))
            selected = comics[0] if comics else None
            chapters = (
                tuple(
                    _chapter_view(chapter)
                    for chapter in repository.list_chapters(selected.id)
                )
                if selected is not None and selected.id is not None
                else ()
            )
            watchlist_entries = tuple(
                _watchlist_entry_view(entry)
                for entry in repository.list_watchlist_entries(limit=50)
            )
            schedule = _watch_schedule_view(
                repository.get_watch_check_schedule(config.source)
            )
    except sqlite3.Error as error:
        return LocalUiState(
            database_path=database_display,
            source=config.source,
            data_status=f"Configured database could not be read: {error}",
        )

    history_rows = _history_rows(
        comics=comics,
        chapters=chapters,
        watchlist_entries=watchlist_entries,
        watch_schedule=schedule,
    )
    if comics or watchlist_entries or chapters or schedule:
        status = (
            f"Loaded local database: {len(comics)} comics, "
            f"{len(watchlist_entries)} watched, {len(chapters)} chapters for the selected comic."
        )
    else:
        status = "Configured database is available but empty."

    return LocalUiState(
        database_path=database_display,
        source=config.source,
        data_status=status,
        comics=comics,
        selected_comic=selected,
        chapters=chapters,
        watchlist_entries=watchlist_entries,
        watch_schedule=schedule,
        history_rows=history_rows,
    )


def sample_local_ui_state() -> LocalUiState:
    """Return the static fallback snapshot used when no explicit state is supplied."""

    first = UiComic(
        id=1,
        source="zaimanhua",
        source_comic_id="15599",
        title="伪恋同盟",
        author="榊葵/绫乃",
        status="已完结",
        latest_chapter_title="第112话",
        detail_url="https://manhua.zaimanhua.com/details/15599",
        last_checked_at="2026-07-20",
        updated_at="2026-07-20",
    )
    second = UiComic(
        id=2,
        source="zaimanhua",
        source_comic_id="251780",
        title="海贼同人短篇合集",
        author="sample",
        latest_chapter_title="第018话",
    )
    chapters = tuple(
        UiChapter(
            title=f"{index:03d}话",
            chapter_order=index,
            chapter_url=f"https://manhua.zaimanhua.com/view/15599/{index:04d}.html",
        )
        for index in range(1, 7)
    )
    return LocalUiState(
        database_path="~/.local/share/panelscout/panelscout.sqlite3",
        source="zaimanhua",
        data_status="Static sample preview; no configured database was loaded.",
        comics=(first, second),
        selected_comic=first,
        chapters=chapters,
        watchlist_entries=(
            UiWatchlistEntry(comic=first, last_checked_at="2026-07-20"),
            UiWatchlistEntry(comic=second),
        ),
        history_rows=(
            UiHistoryRow(kind="New chapter", comic_title=first.title, detail="第003话 重新开始"),
            UiHistoryRow(kind="Metadata", comic_title=first.title, detail="Latest chapter changed"),
            UiHistoryRow(kind="Report", comic_title="watch-check.md", detail="ready for export"),
        ),
    )


def _comic_view(comic: Comic) -> UiComic:
    return UiComic(
        id=comic.id,
        source=comic.source,
        source_comic_id=comic.source_comic_id,
        title=comic.title,
        author=comic.author,
        status=comic.status,
        latest_chapter_title=comic.latest_chapter_title,
        detail_url=comic.detail_url,
        summary=comic.summary,
        last_checked_at=comic.last_checked_at,
        updated_at=comic.updated_at,
    )


def _chapter_view(chapter: Chapter) -> UiChapter:
    return UiChapter(
        title=chapter.title,
        chapter_url=chapter.chapter_url,
        chapter_order=chapter.chapter_order,
    )


def _watchlist_entry_view(entry: WatchlistEntry) -> UiWatchlistEntry:
    return UiWatchlistEntry(
        comic=_comic_view(entry.comic),
        created_at=entry.created_at,
        last_checked_at=entry.last_checked_at,
        notes=entry.notes,
    )


def _watch_schedule_view(schedule: WatchCheckSchedule | None) -> UiWatchSchedule | None:
    if schedule is None:
        return None
    return UiWatchSchedule(
        source=schedule.source,
        interval_minutes=schedule.interval_minutes,
        enabled=schedule.enabled,
        last_run_at=schedule.last_run_at,
        next_run_at=schedule.next_run_at,
    )


def _history_rows(
    *,
    comics: tuple[UiComic, ...],
    chapters: tuple[UiChapter, ...],
    watchlist_entries: tuple[UiWatchlistEntry, ...],
    watch_schedule: UiWatchSchedule | None,
) -> tuple[UiHistoryRow, ...]:
    rows: list[UiHistoryRow] = []
    if watch_schedule is not None:
        rows.append(
            UiHistoryRow(
                kind="Schedule",
                comic_title=watch_schedule.source,
                detail=f"next run {watch_schedule.next_run_at}",
            )
        )
    for entry in watchlist_entries[:4]:
        checked = entry.last_checked_at or "never checked"
        rows.append(
            UiHistoryRow(kind="Watch", comic_title=entry.comic.title, detail=checked)
        )
    for comic in comics[:4]:
        detail = comic.latest_chapter_title or comic.updated_at or "metadata saved"
        rows.append(UiHistoryRow(kind="Catalog", comic_title=comic.title, detail=detail))
    for chapter in chapters[:4]:
        selected_title = comics[0].title if comics else "Selected comic"
        rows.append(UiHistoryRow(kind="Chapter", comic_title=selected_title, detail=chapter.title))
    return tuple(rows[:10])
