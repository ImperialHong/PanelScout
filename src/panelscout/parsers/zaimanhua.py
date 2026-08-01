"""Parsers for ZaiManHua public metadata HTML.

The functions in this module parse saved HTML strings only. They do not fetch
pages, run JavaScript, authenticate, or download comic content.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import json
import re
from urllib.parse import urlparse

from panelscout.adapters.zaimanhua import (
    SOURCE_NAME,
    build_chapter_url,
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


def parse_search_api_response(payload: str | dict[str, object]) -> list[Comic]:
    """Parse ZaiManHua front-end search JSON into comic metadata records."""

    if isinstance(payload, str):
        try:
            document = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ParseError("Could not parse ZaiManHua search API JSON") from error
    else:
        document = payload

    if not isinstance(document, dict):
        raise ParseError("ZaiManHua search API payload must be a JSON object")
    errno = document.get("errno")
    if errno not in (None, 0, "0"):
        raise ParseError(f"ZaiManHua search API returned errno {errno}")

    data = document.get("data")
    items = data.get("list") if isinstance(data, dict) else document.get("list")
    if not isinstance(items, list):
        raise ParseError("ZaiManHua search API response did not include a result list")

    comics: list[Comic] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        comic = _comic_from_search_api_item(item)
        if comic is not None:
            comics.append(comic)
    return comics


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


def parse_detail_api_response(
    payload: str | dict[str, object],
    *,
    detail_url: str | None = None,
) -> ParsedComicDetail:
    """Parse ZaiManHua front-end detail JSON into comic and chapter metadata."""

    if isinstance(payload, str):
        try:
            document = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ParseError("Could not parse ZaiManHua detail API JSON") from error
    else:
        document = payload

    if not isinstance(document, dict):
        raise ParseError("ZaiManHua detail API payload must be a JSON object")
    errno = document.get("errno")
    if errno not in (None, 0, "0"):
        raise ParseError(f"ZaiManHua detail API returned errno {errno}")

    data = document.get("data")
    if not isinstance(data, dict):
        raise ParseError("ZaiManHua detail API response did not include data")
    comic_info = data.get("comicInfo")
    if not isinstance(comic_info, dict):
        raise ParseError("ZaiManHua detail API response did not include comicInfo")

    source_comic_id = (
        _api_text(comic_info.get("id"))
        or extract_source_comic_id(detail_url or "")
        or _api_text(data.get("id"))
    )
    title = (
        _api_text(comic_info.get("title"))
        or _api_text(comic_info.get("comic_name"))
        or _api_text(comic_info.get("name"))
    )
    if not source_comic_id:
        raise ParseError("Could not determine ZaiManHua detail API source comic id")
    if not title:
        raise ParseError("Could not determine ZaiManHua detail API comic title")

    comic_path = _api_text(comic_info.get("comicPy"))
    author_names = _tag_names(comic_info.get("authorsTagList"))
    category_names = _tag_names(comic_info.get("cateTagList"))
    theme_names = _tag_names(comic_info.get("themeTagList"))
    alias_names = _alias_names(comic_info)

    comic = Comic(
        source=SOURCE_NAME,
        source_comic_id=source_comic_id,
        title=title,
        author="/".join(author_names) if author_names else _api_text(comic_info.get("author")),
        status=_first_tag_name(comic_info.get("statusTagList"))
        or _api_text(comic_info.get("status")),
        categories=tuple(category_names),
        tags=tuple(_dedupe_texts((*theme_names, *alias_names))),
        summary=_api_text(comic_info.get("description")),
        latest_chapter_title=_api_text(comic_info.get("lastUpdateChapterName"))
        or _api_text(comic_info.get("last_name")),
        detail_url=normalize_public_url(detail_url) or build_detail_url(source_comic_id),
        cover_url=normalize_public_url(
            _api_text(comic_info.get("cover"))
            or _api_text(comic_info.get("cover_url"))
        ),
    )

    return ParsedComicDetail(
        comic=comic,
        chapters=tuple(
            _api_chapters(
                _api_chapter_list(data, comic_info),
                source_comic_id=source_comic_id,
                comic_path=comic_path,
            )
        ),
    )


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


def _comic_from_search_api_item(item: dict[str, object]) -> Comic | None:
    source_comic_id = _api_text(item.get("id")) or _api_text(item.get("comic_id"))
    title = _api_text(item.get("title"))
    if not source_comic_id or not title:
        return None

    return Comic(
        source=SOURCE_NAME,
        source_comic_id=source_comic_id,
        title=title,
        author=_normalize_author(_api_text(item.get("authors")) or _api_text(item.get("author"))),
        status=_api_text(item.get("status")),
        categories=tuple(_api_text_parts(item.get("types"))),
        tags=tuple(_api_text_parts(item.get("alias_name"))),
        latest_chapter_title=_api_text(item.get("last_update_chapter_name"))
        or _api_text(item.get("last_name")),
        detail_url=build_detail_url(source_comic_id),
        cover_url=normalize_public_url(_api_text(item.get("cover"))),
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
    path = urlparse(href).path if "://" in href else href
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 4 and parts[0] == "view":
        return parts[3]
    if len(parts) >= 3 and parts[0] == "view":
        return parts[2]
    return None


def _api_chapters(
    chapter_list: object,
    *,
    source_comic_id: str,
    comic_path: str | None,
) -> list[ParsedChapter]:
    chapters: list[ParsedChapter] = []
    for item in _iter_chapter_items(chapter_list):
        source_chapter_id = (
            _api_text(item.get("chapter_id"))
            or _api_text(item.get("id"))
            or _api_text(item.get("chapterId"))
        )
        title = (
            _api_text(item.get("chapter_title"))
            or _api_text(item.get("title"))
            or _api_text(item.get("name"))
        )
        if not source_chapter_id or not title:
            continue
        chapters.append(
            ParsedChapter(
                source_chapter_id=source_chapter_id,
                title=title,
                chapter_order=_api_int(item.get("chapter_order")) or len(chapters) + 1,
                chapter_url=build_chapter_url(
                    source_comic_id,
                    source_chapter_id,
                    comic_path=comic_path,
                ),
                published_hint=_api_text(item.get("updatetime"))
                or _api_text(item.get("update_time")),
            )
        )
    return chapters


def _api_chapter_list(
    data: dict[str, object],
    comic_info: dict[str, object],
) -> object:
    if "chapterList" in comic_info:
        return comic_info.get("chapterList")
    if "chapter_list" in comic_info:
        return comic_info.get("chapter_list")
    if "chapters" in comic_info:
        return comic_info.get("chapters")
    if "chapterList" in data:
        return data.get("chapterList")
    if "chapter_list" in data:
        return data.get("chapter_list")
    return data.get("chapters")


def _iter_chapter_items(value: object) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    if isinstance(value, dict):
        chapter_data = value.get("data")
        if isinstance(chapter_data, list):
            values = chapter_data
        else:
            values = list(value.values())
    elif isinstance(value, list):
        values = value
    else:
        values = []

    for entry in values:
        if not isinstance(entry, dict):
            continue
        nested = entry.get("data")
        if isinstance(nested, list):
            items.extend(item for item in nested if isinstance(item, dict))
        elif any(key in entry for key in ("chapter_id", "chapterId", "id")):
            items.append(entry)
    return items


def _tag_names(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    names = []
    for item in value:
        if isinstance(item, dict):
            names.append(_api_text(item.get("tagName")) or _api_text(item.get("name")) or "")
        else:
            names.append(_api_text(item) or "")
    return _dedupe_texts(names)


def _first_tag_name(value: object) -> str | None:
    names = _tag_names(value)
    return names[0] if names else None


def _alias_names(comic_info: dict[str, object]) -> list[str]:
    aliases: list[str] = []
    for key in ("alias_name", "aliasName", "alias"):
        raw = _api_text(comic_info.get(key))
        if raw:
            aliases.extend(part for part in re.split(r"[,，/、]", raw) if part)
    return _dedupe_texts(aliases)


def _api_text_parts(value: object) -> list[str]:
    text = _api_text(value)
    if not text:
        return []
    return _dedupe_texts(part for part in re.split(r"[,，/、]", text) if part)


def _dedupe_texts(values: object) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    if isinstance(values, (str, bytes)):
        raw_values = [values]
    else:
        raw_values = list(values) if values is not None else []
    for value in raw_values:
        text = _api_text(value)
        if text and text not in seen:
            seen.add(text)
            deduped.append(text)
    return deduped


def _api_text(value: object) -> str | None:
    if value is None:
        return None
    text = _clean_text(str(value))
    return text or None


def _api_int(value: object) -> int | None:
    text = _api_text(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except ValueError:
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
