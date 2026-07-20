"""Parsers for ZaiManHua public metadata HTML.

The functions in this module parse saved HTML strings only. They do not fetch
pages, run JavaScript, authenticate, or download comic content.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import re

from panelscout.adapters.zaimanhua import (
    SOURCE_NAME,
    build_detail_url,
    extract_source_comic_id,
    normalize_public_url,
)
from panelscout.storage.models import Comic


@dataclass(frozen=True, kw_only=True)
class ParsedChapter:
    """Parsed source chapter metadata independent of a local database id."""

    source_chapter_id: str | None
    title: str
    chapter_order: int | None
    chapter_url: str
    published_hint: str | None = None


@dataclass(frozen=True, kw_only=True)
class ParsedComicDetail:
    """Parsed public comic details page metadata."""

    comic: Comic
    chapters: tuple[ParsedChapter, ...] = ()


def parse_search_results(html: str) -> list[Comic]:
    """Parse public search/list result cards into comic metadata records."""

    parser = _SearchResultParser()
    parser.feed(html)
    parser.close()
    return parser.comics


def parse_detail_page(html: str, *, detail_url: str | None = None) -> ParsedComicDetail:
    """Parse public comic details metadata and any visible chapter links."""

    head = _HeadMetadataParser()
    head.feed(html)
    head.close()

    page_url = normalize_public_url(
        detail_url
        or head.metas.get("og:url")
        or head.links.get("canonical")
    )
    source_comic_id = extract_source_comic_id(page_url or "") or _extract_id_from_html(html)
    title_source = head.metas.get("og:title") or head.title or ""
    keywords = _split_keywords(head.metas.get("keywords"))
    title, latest_chapter_title, status, author = _parse_detail_title(title_source)

    if not author:
        author = _author_from_keywords(keywords)
    if not latest_chapter_title:
        latest_chapter_title = _latest_from_keywords(keywords)
    if not title:
        title = _title_from_keywords(keywords)
    if not source_comic_id:
        raise ParseError("Could not determine ZaiManHua details source comic id")

    comic = Comic(
        source=SOURCE_NAME,
        source_comic_id=source_comic_id,
        title=title,
        author=author,
        status=status,
        tags=_aliases_from_keywords(title, keywords),
        summary=_summary_from_description(head.metas.get("description") or ""),
        latest_chapter_title=latest_chapter_title,
        detail_url=page_url or build_detail_url(source_comic_id),
        cover_url=_cover_from_meta(head.metas.get("og:image")),
    )

    return ParsedComicDetail(comic=comic, chapters=tuple(_parse_chapter_links(html)))


class ParseError(ValueError):
    """Raised when a saved fixture lacks required public metadata."""


class _SearchResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.comics: list[Comic] = []
        self._card: dict[str, object] | None = None
        self._field: str | None = None
        self._field_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "li":
            self._card = {}
            return

        if self._card is None:
            return

        if tag == "a":
            href = attr.get("href") or ""
            source_id = extract_source_comic_id(href)
            if source_id:
                self._card.setdefault("source_comic_id", source_id)
                self._card.setdefault("detail_url", normalize_public_url(href))
            if attr.get("title"):
                self._card["title"] = _clean_text(attr.get("title") or "")
        elif tag == "img" and attr.get("src"):
            self._card.setdefault("cover_url", normalize_public_url(attr.get("src")))
        elif tag == "p":
            classes = set((attr.get("class") or "").split())
            field = None
            if "auth" in classes:
                field = "author"
            elif "newPage" in classes:
                field = "latest_chapter_title"
            elif "over_comic" in classes:
                field = "status"
            elif "title" in classes:
                field = "title_text"
            if field:
                self._field = field
                self._field_text = []

    def handle_data(self, data: str) -> None:
        if self._field:
            self._field_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._card is not None and tag == "p" and self._field:
            text = _clean_text("".join(self._field_text))
            if self._field == "latest_chapter_title":
                text = text.removeprefix("最新：").strip()
            elif self._field == "status" and text == "完":
                text = "已完结"
            elif self._field == "title_text":
                self._card.setdefault("title", text)
                text = ""
            if text:
                self._card[self._field] = text
            self._field = None
            self._field_text = []
        elif tag == "li" and self._card is not None:
            comic = _comic_from_card(self._card)
            if comic is not None:
                self.comics.append(comic)
            self._card = None
            self._field = None
            self._field_text = []


class _HeadMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.metas: dict[str, str] = {}
        self.links: dict[str, str] = {}
        self.title = ""
        self._in_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "meta":
            key = attr.get("property") or attr.get("name")
            content = attr.get("content")
            if key and content:
                self.metas[key] = unescape(content)
        elif tag == "link" and attr.get("rel") == "canonical" and attr.get("href"):
            self.links["canonical"] = attr["href"] or ""
        elif tag == "title":
            self._in_title = True

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
            self.title = _clean_text("".join(self._title_parts))


def _comic_from_card(card: dict[str, object]) -> Comic | None:
    source_comic_id = str(card.get("source_comic_id") or "")
    title = str(card.get("title") or "")
    if not source_comic_id or not title:
        return None

    return Comic(
        source=SOURCE_NAME,
        source_comic_id=source_comic_id,
        title=title,
        author=_optional_str(card.get("author")),
        status=_optional_str(card.get("status")),
        latest_chapter_title=_optional_str(card.get("latest_chapter_title")),
        detail_url=_optional_str(card.get("detail_url")) or build_detail_url(source_comic_id),
        cover_url=_optional_str(card.get("cover_url")),
    )


def _parse_chapter_links(html: str) -> list[ParsedChapter]:
    parser = _ChapterLinkParser()
    parser.feed(html)
    parser.close()
    return parser.chapters


class _ChapterLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chapters: list[ParsedChapter] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr = dict(attrs)
        href = attr.get("href") or ""
        if "/view/" in href and "undefined" not in href:
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._href:
            return
        title = _clean_text("".join(self._text))
        if title and title not in {"开始阅读", "阅读"}:
            chapter_url = normalize_public_url(self._href)
            if chapter_url:
                source_chapter_id = _extract_source_chapter_id(self._href)
                self.chapters.append(
                    ParsedChapter(
                        source_chapter_id=source_chapter_id,
                        title=title,
                        chapter_order=len(self.chapters) + 1,
                        chapter_url=chapter_url,
                    )
                )
        self._href = None
        self._text = []


def _parse_detail_title(value: str) -> tuple[str, str | None, str | None, str | None]:
    value = _clean_text(value).removesuffix("- 再漫画").strip()
    pattern = re.compile(
        r"^(?P<title>.+?)漫画\s*"
        r"(?P<latest>第[^ ]+?话|番外|全一话|短篇|VOL[_0-9]+)?"
        r"(?P<status>已完结|连载中)?\s*"
        r"(?P<author>.*?)\s*在线漫画"
    )
    match = pattern.search(value)
    if not match:
        return _clean_text(value), None, None, None

    author = _normalize_author(match.group("author"))
    return (
        _clean_text(match.group("title")),
        _clean_text(match.group("latest") or "") or None,
        _clean_text(match.group("status") or "") or None,
        author,
    )


def _author_from_keywords(keywords: list[str]) -> str | None:
    for keyword in keywords:
        if "、" in keyword and "漫画" not in keyword:
            return _normalize_author(keyword)
    return None


def _latest_from_keywords(keywords: list[str]) -> str | None:
    for keyword in keywords:
        match = re.search(r"第[^,， ]+?话|番外|全一话|短篇|VOL[_0-9]+", keyword)
        if match:
            return match.group(0)
    return None


def _title_from_keywords(keywords: list[str]) -> str:
    for keyword in keywords:
        if keyword.endswith("漫画") and len(keyword) > 2:
            return keyword.removesuffix("漫画")
    return ""


def _aliases_from_keywords(title: str, keywords: list[str]) -> tuple[str, ...]:
    aliases = []
    for keyword in keywords:
        if keyword and title and keyword not in {title, f"{title}漫画"}:
            if "漫画" not in keyword and "再漫画" not in keyword and "在线" not in keyword:
                if "、" not in keyword:
                    aliases.append(keyword)
    return tuple(aliases[:3])


def _summary_from_description(description: str) -> str | None:
    description = _clean_text(description)
    if not description:
        return None
    marker = "漫画故事讲述:"
    if marker in description:
        return description.split(marker, 1)[1].strip()
    return description


def _cover_from_meta(value: str | None) -> str | None:
    if not value or "/logo." in value or "/logo/" in value:
        return None
    return normalize_public_url(value)


def _extract_id_from_html(html: str) -> str | None:
    match = re.search(r"/details/(\d+)", html)
    return match.group(1) if match else None


def _extract_source_chapter_id(href: str) -> str | None:
    parts = [part for part in href.split("/") if part]
    if len(parts) >= 3 and parts[0] == "view":
        return parts[2]
    return None


def _split_keywords(value: str | None) -> list[str]:
    if not value:
        return []
    return [_clean_text(part) for part in value.split(",") if _clean_text(part)]


def _normalize_author(value: str | None) -> str | None:
    value = _clean_text(value or "")
    if not value:
        return None
    value = value.replace("、", "/")
    value = re.sub(r"\s+", "/", value)
    return value


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = _clean_text(str(value))
    return text or None
