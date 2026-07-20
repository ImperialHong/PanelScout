"""Crawler support primitives.

The package currently exposes robots-policy checks and an injectable HTML
fetcher baseline. It does not provide site crawling workflows.
"""

from panelscout.crawler.fetcher import (
    FetchBlockedError,
    FetchError,
    FetchHTTPError,
    FetchedHtml,
    HtmlFetcher,
    NonHtmlContentError,
)
from panelscout.crawler.engine import PublicSearchResult, search_public_comics
from panelscout.crawler.robots import RobotsDisallowedError, RobotsPolicy

__all__ = [
    "FetchBlockedError",
    "FetchError",
    "FetchHTTPError",
    "FetchedHtml",
    "HtmlFetcher",
    "NonHtmlContentError",
    "PublicSearchResult",
    "RobotsDisallowedError",
    "RobotsPolicy",
    "search_public_comics",
]
