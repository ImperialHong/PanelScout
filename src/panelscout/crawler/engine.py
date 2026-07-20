"""Small public metadata workflow services.

The functions here compose existing adapter, fetcher, parser, and storage
pieces. They do not create live CLI commands, authenticate, or download content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from panelscout.adapters.zaimanhua import build_search_url
from panelscout.parsers.zaimanhua import parse_search_results
from panelscout.storage.models import Comic
from panelscout.storage.repositories import ComicRepository


@dataclass(frozen=True, kw_only=True)
class PublicSearchResult:
    """Result from one public metadata search workflow."""

    query: str
    url: str
    comics: tuple[Comic, ...]
    persisted_count: int = 0


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


def _response_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    raise TypeError("fetch_html() must return HTML text or an object with .text")
