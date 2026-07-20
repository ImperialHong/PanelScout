"""Small public metadata workflow services.

The functions here compose existing adapter, fetcher, parser, and storage
pieces. They do not authenticate, run browsers, or download content.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from panelscout.adapters.zaimanhua import (
    PUBLIC_DOMAINS,
    build_detail_url,
    build_search_url,
    extract_source_comic_id,
    normalize_public_url,
)
from panelscout.parsers.zaimanhua import ParsedChapter, parse_detail_page, parse_search_results
from panelscout.storage.models import Chapter, Comic
from panelscout.storage.repositories import ComicRepository


@dataclass(frozen=True, kw_only=True)
class PublicSearchResult:
    """Result from one public metadata search workflow."""

    query: str
    url: str
    comics: tuple[Comic, ...]
    persisted_count: int = 0


@dataclass(frozen=True, kw_only=True)
class PublicDetailSyncResult:
    """Result from one public comic detail metadata sync."""

    reference: str
    detail_url: str
    comic: Comic
    chapters: tuple[Chapter, ...]
    new_chapters: tuple[Chapter, ...]
    metadata_changes: tuple[MetadataChange, ...]
    chapter_count: int
    new_chapter_count: int
    existing_chapter_count: int


@dataclass(frozen=True, kw_only=True)
class MetadataChange:
    """One tracked metadata field change from the previous stored comic."""

    field: str
    previous: str | None
    current: str | None


def search_public_comics(
    query: str,
    fetcher: Any,
    *,
    repository: ComicRepository | None = None,
) -> PublicSearchResult:
    """Fetch and parse ZaiManHua public search metadata for a query.

    ``fetcher`` must expose ``fetch_html(url)`` and return either an object with
    a ``text`` attribute or a plain HTML string. Tests inject a fake fetcher;
    this function performs no direct network access by itself.
    """

    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("Search query cannot be blank")

    url = build_search_url(normalized_query)
    response = fetcher.fetch_html(url)
    html = _response_text(response)
    parsed_comics = parse_search_results(html)

    if repository is None:
        return PublicSearchResult(
            query=normalized_query,
            url=url,
            comics=tuple(parsed_comics),
        )

    stored_comics = tuple(repository.upsert_comic(comic) for comic in parsed_comics)
    return PublicSearchResult(
        query=normalized_query,
        url=url,
        comics=stored_comics,
        persisted_count=len(stored_comics),
    )


def sync_public_detail(
    reference: str | int,
    fetcher: Any,
    repository: ComicRepository,
) -> PublicDetailSyncResult:
    """Fetch, parse, and persist one public ZaiManHua details page.

    ``reference`` may be a source comic id, a relative details path, or a
    public ZaiManHua details URL. The injected ``fetcher`` must expose
    ``fetch_html(url)`` and is responsible for robots-aware fetching in live
    callers. This workflow performs no authentication, browser automation, or
    content downloading.
    """

    _source_comic_id, detail_url = normalize_detail_reference(reference)
    response = fetcher.fetch_html(detail_url)
    parsed_detail = parse_detail_page(_response_text(response), detail_url=detail_url)
    previous_comic = repository.get_comic_by_source(
        parsed_detail.comic.source,
        parsed_detail.comic.source_comic_id,
    )
    current_comic = replace(
        parsed_detail.comic,
        last_checked_at=_utc_now(),
    )
    metadata_changes = _comic_metadata_changes(previous_comic, current_comic)

    stored_comic = repository.upsert_comic(current_comic)
    if stored_comic.id is None:
        raise RuntimeError("Comic detail upsert did not return a stored id")

    chapters = tuple(
        _chapter_from_parsed(stored_comic.id, parsed_chapter)
        for parsed_chapter in _dedupe_chapters(parsed_detail.chapters)
    )
    new_chapter_urls = _new_chapter_urls(repository, stored_comic.id, chapters)
    stored_chapters = tuple(repository.upsert_chapters(chapters))
    new_chapters = tuple(
        chapter for chapter in stored_chapters if chapter.chapter_url in new_chapter_urls
    )

    return PublicDetailSyncResult(
        reference=str(reference).strip(),
        detail_url=detail_url,
        comic=stored_comic,
        chapters=stored_chapters,
        new_chapters=new_chapters,
        metadata_changes=metadata_changes,
        chapter_count=len(stored_chapters),
        new_chapter_count=len(new_chapters),
        existing_chapter_count=len(stored_chapters) - len(new_chapters),
    )


def _response_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    raise TypeError("fetch_html() must return HTML text or an object with .text")


def normalize_detail_reference(reference: str | int) -> tuple[str, str]:
    """Return the source comic id and canonical public details URL for a reference."""

    raw_reference = str(reference).strip()
    if not raw_reference:
        raise ValueError("Detail reference cannot be blank")

    parsed_reference = urlparse(raw_reference)
    if parsed_reference.scheme or parsed_reference.netloc:
        if parsed_reference.scheme not in {"http", "https"}:
            raise ValueError("Detail URL must use http or https")
        if parsed_reference.netloc.lower() not in PUBLIC_DOMAINS:
            raise ValueError("Detail URL must be a public ZaiManHua URL")

    normalized_url = normalize_public_url(raw_reference)
    source_comic_id = extract_source_comic_id(normalized_url or raw_reference)
    if source_comic_id is None and raw_reference.isdigit():
        source_comic_id = raw_reference
    if source_comic_id is None:
        raise ValueError("Detail reference must be a source comic id or details URL")

    return source_comic_id, build_detail_url(source_comic_id)


def _dedupe_chapters(chapters: tuple[ParsedChapter, ...]) -> tuple[ParsedChapter, ...]:
    seen_urls: set[str] = set()
    unique_chapters: list[ParsedChapter] = []
    for chapter in chapters:
        if chapter.chapter_url in seen_urls:
            continue
        seen_urls.add(chapter.chapter_url)
        unique_chapters.append(chapter)
    return tuple(unique_chapters)


def _chapter_from_parsed(comic_id: int, parsed_chapter: ParsedChapter) -> Chapter:
    return Chapter(
        comic_id=comic_id,
        source_chapter_id=parsed_chapter.source_chapter_id,
        title=parsed_chapter.title,
        chapter_order=parsed_chapter.chapter_order,
        chapter_url=parsed_chapter.chapter_url,
        published_hint=parsed_chapter.published_hint,
    )


def _new_chapter_urls(
    repository: ComicRepository,
    comic_id: int,
    chapters: tuple[Chapter, ...],
) -> set[str]:
    return {
        chapter.chapter_url
        for chapter in chapters
        if repository.get_chapter_by_url(comic_id, chapter.chapter_url) is None
    }


def _comic_metadata_changes(previous: Comic | None, current: Comic) -> tuple[MetadataChange, ...]:
    if previous is None:
        return ()

    changes: list[MetadataChange] = []
    for field in ("title", "author", "status", "latest_chapter_title"):
        previous_value = getattr(previous, field)
        current_value = getattr(current, field)
        if previous_value != current_value:
            changes.append(
                MetadataChange(
                    field=field,
                    previous=previous_value,
                    current=current_value,
                )
            )
    return tuple(changes)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
