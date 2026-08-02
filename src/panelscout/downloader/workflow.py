"""Download planning and explicit save workflows."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from panelscout.downloader.discovery import parse_public_chapter_images
from panelscout.downloader.planner import (
    DownloadImageCandidate,
    DownloadPlan,
    DownloadPlanItem,
    build_download_plan,
)
from panelscout.storage.models import Chapter, Comic


@dataclass(frozen=True, kw_only=True)
class ChapterDownloadPlanResult:
    comic: Comic
    chapter: Chapter
    images: tuple[DownloadImageCandidate, ...]
    plan: DownloadPlan


@dataclass(frozen=True, kw_only=True)
class DownloadSaveItemResult:
    plan_item: DownloadPlanItem
    status: str
    bytes_written: int = 0
    error: str | None = None


@dataclass(frozen=True, kw_only=True)
class _FetchedPlanItem:
    plan_item: DownloadPlanItem
    content: bytes | None = None
    error: str | None = None


@dataclass(frozen=True, kw_only=True)
class ChapterDownloadSaveResult:
    comic: Comic
    chapter: Chapter
    plan: DownloadPlan
    items: tuple[DownloadSaveItemResult, ...]

    @property
    def saved_count(self) -> int:
        return sum(1 for item in self.items if item.status == "saved")

    @property
    def skipped_count(self) -> int:
        return sum(1 for item in self.items if item.status == "skipped")

    @property
    def failed_count(self) -> int:
        return sum(1 for item in self.items if item.status == "failed")


def plan_public_chapter_download(
    *,
    comic: Comic,
    chapter: Chapter,
    chapter_fetcher: Any,
    download_root: str | Path,
    permission_note: str,
) -> ChapterDownloadPlanResult:
    """Fetch chapter HTML, discover image candidates, and build a local plan."""

    response = chapter_fetcher.fetch_html(chapter.chapter_url)
    html = _response_text(response)
    images = parse_public_chapter_images(html, chapter_url=chapter.chapter_url)
    if not images:
        raise ValueError("No public chapter images were discovered")
    plan = build_download_plan(
        comic=comic,
        chapter=chapter,
        images=images,
        download_root=download_root,
        permission_note=permission_note,
    )
    return ChapterDownloadPlanResult(
        comic=comic,
        chapter=chapter,
        images=images,
        plan=plan,
    )


def save_public_chapter_download(
    *,
    comic: Comic,
    chapter: Chapter,
    chapter_fetcher: Any,
    image_fetcher: Any,
    download_root: str | Path,
    permission_note: str,
    max_image_workers: int = 1,
) -> ChapterDownloadSaveResult:
    """Explicitly save planned public chapter images to local files."""

    planned = plan_public_chapter_download(
        comic=comic,
        chapter=chapter,
        chapter_fetcher=chapter_fetcher,
        download_root=download_root,
        permission_note=permission_note,
    )
    try:
        planned.plan.chapter_directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return ChapterDownloadSaveResult(
            comic=comic,
            chapter=chapter,
            plan=planned.plan,
            items=tuple(
                DownloadSaveItemResult(
                    plan_item=item,
                    status="failed",
                    error=f"could not create chapter directory: {error}",
                )
                for item in planned.plan.items
            ),
        )

    workers = max(1, int(max_image_workers))
    if workers == 1:
        results = [
            _save_fetched_plan_item(_fetch_plan_item(item, image_fetcher=image_fetcher))
            for item in planned.plan.items
        ]
    else:
        results = _save_plan_items_concurrently(
            planned.plan.items,
            image_fetcher=image_fetcher,
            max_workers=workers,
        )

    return ChapterDownloadSaveResult(
        comic=comic,
        chapter=chapter,
        plan=planned.plan,
        items=tuple(results),
    )


def _save_plan_items_concurrently(
    items: tuple[DownloadPlanItem, ...],
    *,
    image_fetcher: Any,
    max_workers: int,
) -> list[DownloadSaveItemResult]:
    fetched_items: list[_FetchedPlanItem | None] = [None] * len(items)
    futures: list[Any | None] = [None] * len(items)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for index, item in enumerate(items):
            if item.action == "skip_existing":
                fetched_items[index] = _FetchedPlanItem(plan_item=item)
                continue
            futures[index] = executor.submit(
                _fetch_plan_item,
                item,
                image_fetcher=image_fetcher,
            )

        results = []
        for index, fetched in enumerate(fetched_items):
            future = futures[index]
            if future is not None:
                fetched = future.result()
            if fetched is not None:
                results.append(_save_fetched_plan_item(fetched))

    return results


def _fetch_plan_item(
    item: DownloadPlanItem,
    *,
    image_fetcher: Any,
) -> _FetchedPlanItem:
    if item.action == "skip_existing":
        return _FetchedPlanItem(plan_item=item)

    try:
        fetched = image_fetcher.fetch_image(item.source_url)
        content = _response_bytes(fetched)
    except Exception as error:  # noqa: BLE001 - continue saving independent pages.
        return _FetchedPlanItem(plan_item=item, error=str(error))

    return _FetchedPlanItem(plan_item=item, content=content)


def _save_fetched_plan_item(fetched: _FetchedPlanItem) -> DownloadSaveItemResult:
    item = fetched.plan_item
    if item.action == "skip_existing":
        return DownloadSaveItemResult(plan_item=item, status="skipped")
    if fetched.error is not None:
        return DownloadSaveItemResult(
            plan_item=item,
            status="failed",
            error=fetched.error,
        )

    content = fetched.content or b""
    try:
        item.temporary_path.write_bytes(content)
        item.temporary_path.replace(item.target_path)
    except Exception as error:  # noqa: BLE001 - continue saving independent pages.
        return DownloadSaveItemResult(
            plan_item=item,
            status="failed",
            error=str(error),
        )

    return DownloadSaveItemResult(
        plan_item=item,
        status="saved",
        bytes_written=len(content),
    )


def _response_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    raise TypeError("fetch_html() must return HTML text or an object with .text")


def _response_bytes(response: Any) -> bytes:
    if isinstance(response, bytes):
        return response
    content = getattr(response, "content", None)
    if isinstance(content, bytes):
        return content
    raise TypeError("fetch_image() must return bytes or an object with .content")
