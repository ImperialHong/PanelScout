"""Read local chapter download status without fetching network resources."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from panelscout.downloader.planner import KNOWN_IMAGE_EXTENSIONS, safe_path_segment
from panelscout.storage.models import Chapter, Comic


@dataclass(frozen=True, kw_only=True)
class DownloadedFileStatus:
    """One local file found in a chapter download directory."""

    name: str
    path: Path
    size_bytes: int
    kind: str


@dataclass(frozen=True, kw_only=True)
class ChapterDownloadStatus:
    """Local filesystem status for one comic chapter directory."""

    download_root: Path
    comic_directory: Path
    chapter_directory: Path
    directory_exists: bool
    files: tuple[DownloadedFileStatus, ...]

    @property
    def complete_count(self) -> int:
        return sum(1 for item in self.files if item.kind == "complete")

    @property
    def partial_count(self) -> int:
        return sum(1 for item in self.files if item.kind == "partial")

    @property
    def state(self) -> str:
        if not self.directory_exists:
            return "not_started"
        if self.partial_count:
            return "partial"
        if self.complete_count:
            return "complete"
        return "empty"


def read_chapter_download_status(
    *,
    comic: Comic,
    chapter: Chapter,
    download_root: str | Path,
) -> ChapterDownloadStatus:
    """Return local saved/partial file status for a chapter.

    This only reads the expected directory derived from the same path rules as
    the download planner. It does not fetch chapter HTML and does not infer a
    remote page count.
    """

    root = Path(download_root).expanduser()
    comic_directory = root / safe_path_segment(
        comic.title,
        fallback=f"{comic.source}-{comic.source_comic_id}",
    )
    chapter_directory = comic_directory / safe_path_segment(
        chapter.title,
        fallback=_chapter_fallback(chapter),
    )

    files: list[DownloadedFileStatus] = []
    if chapter_directory.is_dir():
        for path in sorted(chapter_directory.iterdir(), key=lambda item: item.name):
            if not path.is_file():
                continue
            kind = _file_kind(path)
            if kind is None:
                continue
            files.append(
                DownloadedFileStatus(
                    name=path.name,
                    path=path,
                    size_bytes=path.stat().st_size,
                    kind=kind,
                )
            )

    return ChapterDownloadStatus(
        download_root=root,
        comic_directory=comic_directory,
        chapter_directory=chapter_directory,
        directory_exists=chapter_directory.is_dir(),
        files=tuple(files),
    )


def _file_kind(path: Path) -> str | None:
    if path.name.endswith(".part"):
        return "partial"
    extension = path.suffix.lower().lstrip(".")
    if extension in KNOWN_IMAGE_EXTENSIONS:
        return "complete"
    return None


def _chapter_fallback(chapter: Chapter) -> str:
    if chapter.chapter_order is not None:
        return f"{chapter.chapter_order:03d}话"
    if chapter.source_chapter_id:
        return chapter.source_chapter_id
    if chapter.id is not None:
        return f"chapter-{chapter.id}"
    return "001话"
