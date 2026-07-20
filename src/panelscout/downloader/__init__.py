"""Download planning helpers for PanelScout."""

from panelscout.downloader.discovery import parse_public_chapter_images
from panelscout.downloader.fetcher import FetchedImage, ImageFetcher, NonImageContentError
from panelscout.downloader.planner import (
    DownloadImageCandidate,
    DownloadPlan,
    DownloadPlanItem,
    build_download_plan,
    infer_image_extension,
    safe_path_segment,
)
from panelscout.downloader.workflow import (
    ChapterDownloadPlanResult,
    ChapterDownloadSaveResult,
    DownloadSaveItemResult,
    plan_public_chapter_download,
    save_public_chapter_download,
)

__all__ = [
    "ChapterDownloadPlanResult",
    "ChapterDownloadSaveResult",
    "DownloadImageCandidate",
    "DownloadPlan",
    "DownloadPlanItem",
    "DownloadSaveItemResult",
    "FetchedImage",
    "ImageFetcher",
    "NonImageContentError",
    "build_download_plan",
    "infer_image_extension",
    "parse_public_chapter_images",
    "plan_public_chapter_download",
    "safe_path_segment",
    "save_public_chapter_download",
]
