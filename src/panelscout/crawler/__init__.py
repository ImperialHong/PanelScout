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
from panelscout.crawler.engine import (
    PublicDetailSyncResult,
    PublicSearchResult,
    normalize_detail_reference,
    search_public_comics,
    sync_public_detail,
)
from panelscout.crawler.robots import (
    RobotsDisallowedError,
    RobotsLoadError,
    RobotsPolicy,
    load_robots_policy,
)

__all__ = [
    "FetchBlockedError",
    "FetchError",
    "FetchHTTPError",
    "FetchedHtml",
    "HtmlFetcher",
    "NonHtmlContentError",
    "PublicDetailSyncResult",
    "PublicSearchResult",
    "RobotsDisallowedError",
    "RobotsLoadError",
    "RobotsPolicy",
    "load_robots_policy",
    "normalize_detail_reference",
    "search_public_comics",
    "sync_public_detail",
]
