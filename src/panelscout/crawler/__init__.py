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
from panelscout.crawler.robots import RobotsDisallowedError, RobotsPolicy

__all__ = [
    "FetchBlockedError",
    "FetchError",
    "FetchHTTPError",
    "FetchedHtml",
    "HtmlFetcher",
    "NonHtmlContentError",
    "RobotsDisallowedError",
    "RobotsPolicy",
]
