"""Public chapter image discovery from saved HTML."""

from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import json
import re
from urllib.parse import urljoin

from panelscout.downloader.planner import (
    KNOWN_IMAGE_EXTENSIONS,
    DownloadImageCandidate,
    infer_image_extension,
)


IMAGE_FIELD_NAMES = {
    "src",
    "data-src",
    "data-original",
    "data-url",
    "data-image",
    "data-lazy-src",
}
SCRIPT_IMAGE_PATTERN = re.compile(
    r"""["'](?P<url>[^"']+\.(?:jpg|jpeg|png|webp|gif|bmp|avif)(?:\?[^"']*)?)["']""",
    re.IGNORECASE,
)


def parse_public_chapter_images(
    html: str,
    *,
    chapter_url: str,
) -> tuple[DownloadImageCandidate, ...]:
    """Parse public chapter image candidates from a saved chapter HTML string.

    The parser is intentionally fixture/string based. It never fetches pages,
    evaluates JavaScript, authenticates, or downloads image content.
    """

    parser = _ChapterImageParser(chapter_url=chapter_url)
    parser.feed(html)
    parser.close()

    candidates = list(parser.images)
    candidates.extend(_script_candidates(html, chapter_url=chapter_url))
    return tuple(_dedupe_candidates(candidates))


class _ChapterImageParser(HTMLParser):
    def __init__(self, *, chapter_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.chapter_url = chapter_url
        self.images: list[DownloadImageCandidate] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in {"img", "source"}:
            return

        attr = dict(attrs)
        for field_name in IMAGE_FIELD_NAMES:
            raw_url = attr.get(field_name)
            if raw_url:
                self._append(raw_url, page_hint=attr.get("data-page"))
                return

        srcset = attr.get("srcset") or attr.get("data-srcset")
        if srcset:
            first_url = srcset.split(",", 1)[0].strip().split(" ", 1)[0]
            if first_url:
                self._append(first_url, page_hint=attr.get("data-page"))

    def _append(self, raw_url: str, *, page_hint: str | None) -> None:
        candidate = _candidate_from_url(
            raw_url,
            chapter_url=self.chapter_url,
            page_number=_positive_int(page_hint),
        )
        if candidate is not None:
            self.images.append(candidate)


def _script_candidates(
    html: str,
    *,
    chapter_url: str,
) -> list[DownloadImageCandidate]:
    candidates: list[DownloadImageCandidate] = []
    for match in SCRIPT_IMAGE_PATTERN.finditer(html):
        candidate = _candidate_from_url(match.group("url"), chapter_url=chapter_url)
        if candidate is not None:
            candidates.append(candidate)

    for raw_url in _json_image_values(html):
        candidate = _candidate_from_url(raw_url, chapter_url=chapter_url)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _json_image_values(html: str) -> list[str]:
    values: list[str] = []
    for marker in ("__PANELSCOUT_CHAPTER_IMAGES__",):
        index = html.find(marker)
        if index < 0:
            continue
        start = html.find("[", index)
        end = html.find("]", start)
        if start < 0 or end < 0:
            continue
        try:
            decoded = json.loads(html[start : end + 1])
        except json.JSONDecodeError:
            continue
        values.extend(_flatten_json_strings(decoded))
    return values


def _flatten_json_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(_flatten_json_strings(item))
        return items
    if isinstance(value, dict):
        items = []
        for key in ("url", "src", "image", "imageUrl"):
            items.extend(_flatten_json_strings(value.get(key)))
        return items
    return []


def _candidate_from_url(
    raw_url: str,
    *,
    chapter_url: str,
    page_number: int | None = None,
) -> DownloadImageCandidate | None:
    source_url = urljoin(chapter_url, unescape(raw_url.strip()))
    if not source_url.startswith(("http://", "https://")):
        return None
    candidate = DownloadImageCandidate(
        source_url=source_url,
        page_number=page_number,
    )
    extension = infer_image_extension(candidate)
    if extension == "bin" or extension not in KNOWN_IMAGE_EXTENSIONS:
        return None
    return DownloadImageCandidate(
        source_url=source_url,
        extension=extension,
        page_number=page_number,
    )


def _dedupe_candidates(
    candidates: list[DownloadImageCandidate],
) -> list[DownloadImageCandidate]:
    deduped: list[DownloadImageCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.source_url in seen:
            continue
        seen.add(candidate.source_url)
        deduped.append(
            DownloadImageCandidate(
                source_url=candidate.source_url,
                extension=candidate.extension,
                page_number=candidate.page_number or len(deduped) + 1,
                source_page_id=candidate.source_page_id,
            )
        )
    return deduped


def _positive_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None
