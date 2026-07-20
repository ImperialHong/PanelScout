"""Local download plan construction.

This module only plans local file targets. It never fetches pages, downloads
images, creates directories, or writes files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from urllib.parse import urlparse

from panelscout.storage.models import Chapter, Comic


INVALID_PATH_CHARS = re.compile(r'[\\/:\*\?"<>\|\x00-\x1f]')
WHITESPACE = re.compile(r"\s+")
KNOWN_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif", "bmp", "avif"}


@dataclass(frozen=True, kw_only=True)
class DownloadImageCandidate:
    """A future image download target discovered from a chapter page."""

    source_url: str
    extension: str | None = None
    page_number: int | None = None
    source_page_id: str | None = None


@dataclass(frozen=True, kw_only=True)
class DownloadPlanItem:
    """One local file target in a download plan."""

    page_number: int
    source_url: str
    target_path: Path
    temporary_path: Path
    relative_path: Path
    extension: str
    action: str
    source_page_id: str | None = None


@dataclass(frozen=True, kw_only=True)
class DownloadPlan:
    """A local chapter download plan."""

    source: str
    source_comic_id: str
    comic_title: str
    chapter_title: str
    download_root: Path
    comic_directory: Path
    chapter_directory: Path
    permission_note: str
    items: tuple[DownloadPlanItem, ...]


def build_download_plan(
    *,
    comic: Comic,
    chapter: Chapter,
    images: tuple[DownloadImageCandidate, ...],
    download_root: str | Path,
    permission_note: str,
) -> DownloadPlan:
    """Plan local file paths for one chapter.

    The permission note is required so later execution can keep a local audit
    trail that this plan was built for user-authorized personal archiving.
    """

    note = permission_note.strip()
    if not note:
        raise ValueError("download permission note is required")

    root = Path(download_root).expanduser()
    comic_segment = safe_path_segment(
        comic.title,
        fallback=f"{comic.source}-{comic.source_comic_id}",
    )
    chapter_segment = safe_path_segment(
        chapter.title,
        fallback=_chapter_fallback(chapter),
    )
    comic_directory = root / comic_segment
    chapter_directory = comic_directory / chapter_segment

    used_names: set[str] = set()
    items = []
    for index, image in enumerate(images, start=1):
        page_number = image.page_number if image.page_number is not None else index
        if page_number < 1:
            raise ValueError("download page numbers must be positive")
        extension = infer_image_extension(image)
        filename = _unique_filename(f"{page_number:03d}.{extension}", used_names)
        target_path = chapter_directory / filename
        temporary_path = target_path.with_name(f"{target_path.name}.part")
        items.append(
            DownloadPlanItem(
                page_number=page_number,
                source_url=image.source_url,
                target_path=target_path,
                temporary_path=temporary_path,
                relative_path=target_path.relative_to(root),
                extension=extension,
                action=_plan_action(target_path, temporary_path),
                source_page_id=image.source_page_id,
            )
        )

    return DownloadPlan(
        source=comic.source,
        source_comic_id=comic.source_comic_id,
        comic_title=comic.title,
        chapter_title=chapter.title,
        download_root=root,
        comic_directory=comic_directory,
        chapter_directory=chapter_directory,
        permission_note=note,
        items=tuple(items),
    )


def safe_path_segment(value: str | None, *, fallback: str) -> str:
    """Return a conservative filesystem-safe path segment."""

    cleaned = INVALID_PATH_CHARS.sub("_", value or "")
    cleaned = WHITESPACE.sub(" ", cleaned).strip(" .")
    if not cleaned or not cleaned.strip("_ "):
        cleaned = INVALID_PATH_CHARS.sub("_", fallback).strip(" .")
    return cleaned[:120] or "untitled"


def infer_image_extension(image: DownloadImageCandidate) -> str:
    """Infer and normalize a file extension without fetching the image."""

    explicit = _normalize_extension(image.extension)
    if explicit is not None:
        return explicit

    path = urlparse(image.source_url).path
    suffix = Path(path).suffix
    inferred = _normalize_extension(suffix)
    return inferred or "bin"


def _normalize_extension(value: str | None) -> str | None:
    if value is None:
        return None
    extension = value.strip().lower().lstrip(".")
    if not extension or not extension.isascii() or not extension.isalnum():
        return None
    if extension == "jpeg":
        return "jpg"
    if extension in KNOWN_IMAGE_EXTENSIONS:
        return extension
    return extension[:12]


def _unique_filename(filename: str, used_names: set[str]) -> str:
    if filename not in used_names:
        used_names.add(filename)
        return filename

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 2
    while True:
        candidate = f"{stem}-{counter}{suffix}"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        counter += 1


def _plan_action(target_path: Path, temporary_path: Path) -> str:
    if target_path.exists():
        return "skip_existing"
    if temporary_path.exists():
        return "resume_partial"
    return "download"


def _chapter_fallback(chapter: Chapter) -> str:
    if chapter.chapter_order is not None:
        return f"{chapter.chapter_order:03d}话"
    if chapter.source_chapter_id:
        return chapter.source_chapter_id
    if chapter.id is not None:
        return f"chapter-{chapter.id}"
    return "001话"
