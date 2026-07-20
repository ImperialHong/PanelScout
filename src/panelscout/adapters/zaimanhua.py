"""ZaiManHua public URL helpers.

This module only builds and normalizes public page URLs. It does not fetch,
crawl, authenticate, or download content.
"""

SOURCE_NAME = "zaimanhua"
PUBLIC_BASE_URL = "https://manhua.zaimanhua.com"
PUBLIC_DOMAINS = ("manhua.zaimanhua.com", "www.zaimanhua.com", "zaimanhua.com")

from urllib.parse import quote, urljoin, urlparse, urlunparse


def build_detail_url(source_comic_id: str | int) -> str:
    """Build a public comic details URL."""

    return f"{PUBLIC_BASE_URL}/details/{source_comic_id}"


def build_search_url(query: str) -> str:
    """Build a public dynamic search URL for a keyword."""

    return f"{PUBLIC_BASE_URL}/dynamic/{quote(query.strip())}"


def build_robots_url() -> str:
    """Build the public robots.txt URL."""

    return f"{PUBLIC_BASE_URL}/robots.txt"


def extract_source_comic_id(url: str) -> str | None:
    """Return the source comic id from a details URL when present."""

    path_parts = [part for part in urlparse(url).path.split("/") if part]
    if len(path_parts) >= 2 and path_parts[0] in {"details", "detail"}:
        return path_parts[1]
    return None


def normalize_public_url(url: str | None) -> str | None:
    """Normalize a public ZaiManHua URL or path to the canonical public host."""

    if not url:
        return None

    parsed = urlparse(urljoin(PUBLIC_BASE_URL, url))
    if parsed.scheme not in {"http", "https"}:
        return None

    host = parsed.netloc.lower()
    if host not in PUBLIC_DOMAINS:
        return urlunparse(parsed)

    return urlunparse(
        (
            "https",
            urlparse(PUBLIC_BASE_URL).netloc,
            parsed.path,
            "",
            parsed.query,
            "",
        )
    )


__all__ = [
    "PUBLIC_BASE_URL",
    "PUBLIC_DOMAINS",
    "SOURCE_NAME",
    "build_detail_url",
    "build_robots_url",
    "build_search_url",
    "extract_source_comic_id",
    "normalize_public_url",
]
