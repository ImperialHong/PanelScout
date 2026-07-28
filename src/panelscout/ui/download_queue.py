"""In-memory background download queue for the local UI runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Condition, Thread
from time import monotonic
from typing import Any, Callable
from uuid import uuid4


DownloadRunner = Callable[[dict[str, Any]], dict[str, Any]]

ACTIVE_STATUSES = {"pending", "running"}
PASSWORD_KEYS = {"password", "username"}


def _utc_now_string() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DownloadQueueJob:
    """One queued chapter download task."""

    payload: dict[str, Any]
    source: str
    source_comic_id: str
    comic_title: str
    chapter_title: str
    output_root: str
    id: str = field(default_factory=lambda: uuid4().hex)
    status: str = "pending"
    created_at: str = field(default_factory=_utc_now_string)
    updated_at: str = field(default_factory=_utc_now_string)
    started_at: str | None = None
    finished_at: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = self.result or {}
        download_status = result.get("download_status") or {}
        return {
            "id": self.id,
            "status": self.status,
            "status_label": _status_label(self.status),
            "ok": _job_ok(self),
            "source": self.source,
            "source_comic_id": self.source_comic_id,
            "comic_title": self.comic_title,
            "chapter_title": self.chapter_title,
            "output_root": self.output_root,
            "chapter_directory": result.get("chapter_directory")
            or download_status.get("chapter_directory"),
            "saved_count": result.get("saved_count"),
            "skipped_count": result.get("skipped_count"),
            "failed_count": result.get("failed_count"),
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": result if self.status in {"complete", "failed"} else None,
        }


class DownloadQueue:
    """Thread-safe sequential background queue."""

    def __init__(self, runner: DownloadRunner, *, max_history: int = 500) -> None:
        self._runner = runner
        self._max_history = max_history
        self._condition = Condition()
        self._jobs: list[DownloadQueueJob] = []
        self._worker: Thread | None = None

    def add(self, job: DownloadQueueJob) -> dict[str, Any]:
        with self._condition:
            self._jobs.append(job)
            self._trim_completed_history_locked()
            self._ensure_worker_locked()
            self._condition.notify_all()
            return job.to_dict()

    def snapshot(self) -> dict[str, Any]:
        with self._condition:
            jobs = [job.to_dict() for job in self._jobs]
        return {
            "jobs": jobs,
            "summary": _queue_summary(jobs),
        }

    def wait_until_idle(self, timeout_seconds: float = 5.0) -> bool:
        deadline = monotonic() + timeout_seconds
        with self._condition:
            while any(job.status in ACTIVE_STATUSES for job in self._jobs):
                remaining = deadline - monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True

    def _ensure_worker_locked(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._worker = Thread(target=self._run_worker, daemon=True)
        self._worker.start()

    def _run_worker(self) -> None:
        while True:
            with self._condition:
                job = self._next_pending_job_locked()
                if job is None:
                    self._worker = None
                    self._condition.notify_all()
                    return
                job.status = "running"
                job.started_at = _utc_now_string()
                job.updated_at = job.started_at
                self._condition.notify_all()

            try:
                result = self._runner(dict(job.payload))
            except Exception as error:  # noqa: BLE001 - queue must record task failures.
                with self._condition:
                    job.status = "failed"
                    job.error = str(error)
                    job.finished_at = _utc_now_string()
                    job.updated_at = job.finished_at
                    self._condition.notify_all()
                continue

            with self._condition:
                job.result = result
                job.status = "complete" if result.get("ok") else "failed"
                if job.status == "failed":
                    job.error = _result_error(result)
                job.finished_at = _utc_now_string()
                job.updated_at = job.finished_at
                self._condition.notify_all()

    def _next_pending_job_locked(self) -> DownloadQueueJob | None:
        for job in self._jobs:
            if job.status == "pending":
                return job
        return None

    def _trim_completed_history_locked(self) -> None:
        if len(self._jobs) <= self._max_history:
            return
        removable = len(self._jobs) - self._max_history
        kept: list[DownloadQueueJob] = []
        for job in self._jobs:
            if removable and job.status not in ACTIVE_STATUSES:
                removable -= 1
                continue
            kept.append(job)
        self._jobs = kept


def build_queue_job(
    *,
    payload: dict[str, Any],
    source: str,
    source_comic_id: str,
    comic_title: str,
    chapter_title: str,
    output_root: str,
) -> DownloadQueueJob:
    return DownloadQueueJob(
        payload=_sanitized_payload(payload),
        source=source,
        source_comic_id=source_comic_id,
        comic_title=comic_title,
        chapter_title=chapter_title,
        output_root=output_root,
    )


def _sanitized_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key not in PASSWORD_KEYS}


def _status_label(status: str) -> str:
    return {
        "pending": "等待中",
        "running": "下载中",
        "complete": "已完成",
        "failed": "需处理",
    }.get(status, status)


def _job_ok(job: DownloadQueueJob) -> bool | None:
    if job.status == "complete":
        return True
    if job.status == "failed":
        return False
    return None


def _queue_summary(jobs: list[dict[str, Any]]) -> dict[str, int | bool]:
    pending = sum(1 for job in jobs if job["status"] == "pending")
    running = sum(1 for job in jobs if job["status"] == "running")
    complete = sum(1 for job in jobs if job["status"] == "complete")
    failed = sum(1 for job in jobs if job["status"] == "failed")
    return {
        "total": len(jobs),
        "pending": pending,
        "running": running,
        "complete": complete,
        "failed": failed,
        "active": pending + running > 0,
    }


def _result_error(result: dict[str, Any]) -> str | None:
    failed_count = result.get("failed_count")
    if failed_count:
        return f"{failed_count} file(s) failed"
    return result.get("error")

