"""Local UI API services for the PanelScout runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from panelscout.adapters.zaimanhua import SOURCE_NAME, build_robots_url
from panelscout.config import PanelScoutConfig
from panelscout.crawler import (
    FetchError,
    HtmlFetcher,
    RobotsDisallowedError,
    RobotsLoadError,
    load_robots_policy,
    normalize_detail_reference,
    search_public_comics,
    sync_public_detail,
)
from panelscout.downloader import (
    ImageFetcher,
    read_chapter_download_status,
    plan_public_chapter_download,
    save_public_chapter_download,
)
from panelscout.storage import ComicRepository, connect_database
from panelscout.storage.models import Chapter, Comic
from panelscout.ui.state import LocalUiState, build_local_ui_state


FetcherFactory = Callable[[PanelScoutConfig], Any]


class UiApiError(ValueError):
    """API-facing error with an HTTP-like status code."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True, kw_only=True)
class UiApiFactories:
    search_fetcher_factory: FetcherFactory | None = None
    sync_fetcher_factory: FetcherFactory | None = None
    download_fetcher_factory: FetcherFactory | None = None
    image_fetcher_factory: FetcherFactory | None = None


class PanelScoutUiApi:
    """Small local API facade used by the interactive UI runner."""

    def __init__(
        self,
        config: PanelScoutConfig,
        *,
        factories: UiApiFactories | None = None,
    ) -> None:
        self.config = config
        self.factories = factories or UiApiFactories()

    def state(self) -> dict[str, Any]:
        state = build_local_ui_state(self.config)
        return {
            "ok": True,
            "state": _state_dict(state),
        }

    def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = _required_string(payload, "query")
        save = bool(payload.get("save", True))
        factory = self.factories.search_fetcher_factory or _create_html_fetcher
        try:
            fetcher = factory(self.config)
            if save:
                with connect_database(self.config.database_path) as connection:
                    result = search_public_comics(
                        query,
                        fetcher,
                        repository=ComicRepository(connection),
                    )
            else:
                result = search_public_comics(query, fetcher)
        except ValueError as error:
            raise UiApiError(str(error), status_code=400) from error
        except (RobotsLoadError, RobotsDisallowedError, FetchError) as error:
            raise UiApiError(str(error), status_code=502) from error

        return {
            "ok": True,
            "saved": save,
            "query": result.query,
            "source_url": result.url,
            "persisted_count": result.persisted_count,
            "comics": [_comic_dict(comic) for comic in result.comics],
            "state": _state_dict(build_local_ui_state(self.config)),
        }

    def sync(self, payload: dict[str, Any]) -> dict[str, Any]:
        reference = _required_string(payload, "reference")
        save = bool(payload.get("save", True))
        try:
            normalize_detail_reference(reference)
        except ValueError as error:
            raise UiApiError(str(error), status_code=400) from error

        factory = self.factories.sync_fetcher_factory or _create_html_fetcher
        database_path = self.config.database_path if save else ":memory:"
        try:
            fetcher = factory(self.config)
            with connect_database(database_path) as connection:
                result = sync_public_detail(
                    reference,
                    fetcher,
                    ComicRepository(connection),
                )
        except ValueError as error:
            raise UiApiError(str(error), status_code=400) from error
        except (RobotsLoadError, RobotsDisallowedError, FetchError) as error:
            raise UiApiError(str(error), status_code=502) from error

        return {
            "ok": True,
            "saved": save,
            "comic": _comic_dict(result.comic),
            "chapters": [_chapter_dict(chapter) for chapter in result.chapters],
            "new_chapter_count": result.new_chapter_count,
            "existing_chapter_count": result.existing_chapter_count,
            "metadata_changes": [asdict(change) for change in result.metadata_changes],
            "state": _state_dict(build_local_ui_state(self.config)),
        }

    def download_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        source, comic, chapter = self._load_selection(payload)
        permission_note = _required_string(payload, "permission_note")
        download_root = _download_root(payload, self.config)
        factory = self.factories.download_fetcher_factory or _create_html_fetcher
        try:
            result = plan_public_chapter_download(
                comic=comic,
                chapter=chapter,
                chapter_fetcher=factory(self.config),
                download_root=download_root,
                permission_note=permission_note,
            )
        except ValueError as error:
            raise UiApiError(str(error), status_code=400) from error
        except (RobotsLoadError, RobotsDisallowedError, FetchError) as error:
            raise UiApiError(str(error), status_code=502) from error

        return {
            "ok": True,
            "source": source,
            "comic": _comic_dict(comic),
            "chapter": _chapter_dict(chapter),
            "images_discovered": len(result.images),
            "download_root": str(result.plan.download_root),
            "chapter_directory": str(result.plan.chapter_directory),
            "items": [_plan_item_dict(item) for item in result.plan.items],
        }

    def download_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        source, comic, chapter = self._load_selection(payload)
        permission_note = _required_string(payload, "permission_note")
        download_root = _download_root(payload, self.config)
        download_factory = self.factories.download_fetcher_factory or _create_html_fetcher
        image_factory = self.factories.image_fetcher_factory or _create_image_fetcher
        try:
            result = save_public_chapter_download(
                comic=comic,
                chapter=chapter,
                chapter_fetcher=download_factory(self.config),
                image_fetcher=image_factory(self.config),
                download_root=download_root,
                permission_note=permission_note,
            )
        except ValueError as error:
            raise UiApiError(str(error), status_code=400) from error
        except (RobotsLoadError, RobotsDisallowedError, FetchError) as error:
            raise UiApiError(str(error), status_code=502) from error

        return {
            "ok": result.failed_count == 0,
            "source": source,
            "comic": _comic_dict(comic),
            "chapter": _chapter_dict(chapter),
            "chapter_directory": str(result.plan.chapter_directory),
            "saved_count": result.saved_count,
            "skipped_count": result.skipped_count,
            "failed_count": result.failed_count,
            "items": [
                {
                    "page_number": item.plan_item.page_number,
                    "relative_path": str(item.plan_item.relative_path),
                    "status": item.status,
                    "bytes_written": item.bytes_written,
                    "error": item.error,
                }
                for item in result.items
            ],
            "download_status": self.download_status(payload)["download_status"],
        }

    def download_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        source, comic, chapter = self._load_selection(payload)
        root = Path(_download_root(payload, self.config)).expanduser()
        status = read_chapter_download_status(
            comic=comic,
            chapter=chapter,
            download_root=root,
        )
        image_files = [item.name for item in status.files if item.kind == "complete"]
        partial_files = [item.name for item in status.files if item.kind == "partial"]

        return {
            "ok": True,
            "source": source,
            "comic": _comic_dict(comic),
            "chapter": _chapter_dict(chapter),
            "download_status": {
                "exists": status.directory_exists,
                "download_root": str(status.download_root),
                "chapter_directory": str(status.chapter_directory),
                "saved_count": status.complete_count,
                "partial_count": status.partial_count,
                "state": status.state,
                "label": _download_status_label(status.state),
                "files": image_files,
                "partials": partial_files,
            },
        }

    def _load_selection(self, payload: dict[str, Any]) -> tuple[str, Comic, Chapter]:
        source = str(payload.get("source") or self.config.source)
        if source != SOURCE_NAME:
            raise UiApiError(f"unsupported source: {source}", status_code=400)

        source_comic_id = _required_string(payload, "source_comic_id")
        chapter_reference = _required_string(payload, "chapter")
        database_path = Path(self.config.database_path).expanduser()
        if str(self.config.database_path) != ":memory:" and not database_path.exists():
            raise UiApiError(
                "local database not found; run search and sync first",
                status_code=404,
            )

        with connect_database(self.config.database_path) as connection:
            repository = ComicRepository(connection)
            comic = repository.get_comic_by_source(source, source_comic_id)
            if comic is None or comic.id is None:
                raise UiApiError(f"local comic not found: {source_comic_id}", status_code=404)
            chapter = _select_chapter(repository.list_chapters(comic.id), chapter_reference)
            if chapter is None:
                raise UiApiError(f"local chapter not found: {chapter_reference}", status_code=404)
            return source, comic, chapter


def _create_html_fetcher(config: PanelScoutConfig) -> HtmlFetcher:
    robots_policy = load_robots_policy(
        build_robots_url(),
        user_agent=config.user_agent,
    )
    return HtmlFetcher(config=config, robots_policy=robots_policy)


def _create_image_fetcher(config: PanelScoutConfig) -> ImageFetcher:
    return ImageFetcher(config=config)


def _state_dict(state: LocalUiState) -> dict[str, Any]:
    return asdict(state)


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if value is None:
        raise UiApiError(f"{key} is required", status_code=400)
    normalized = str(value).strip()
    if not normalized:
        raise UiApiError(f"{key} cannot be blank", status_code=400)
    return normalized


def _download_root(payload: dict[str, Any], config: PanelScoutConfig) -> str | Path:
    value = payload.get("output_root")
    if value is None:
        return config.download_root
    normalized = str(value).strip()
    if not normalized:
        raise UiApiError("output_root cannot be blank", status_code=400)
    return normalized


def _comic_dict(comic: Comic) -> dict[str, Any]:
    return asdict(comic)


def _chapter_dict(chapter: Chapter) -> dict[str, Any]:
    return asdict(chapter)


def _plan_item_dict(item: Any) -> dict[str, Any]:
    return {
        "page_number": item.page_number,
        "source_url": item.source_url,
        "relative_path": str(item.relative_path),
        "target_path": str(item.target_path),
        "temporary_path": str(item.temporary_path),
        "extension": item.extension,
        "action": item.action,
    }


def _select_chapter(chapters: list[Chapter], reference: str) -> Chapter | None:
    normalized = reference.strip()
    for chapter in chapters:
        candidates = {
            chapter.title,
            chapter.chapter_url,
            str(chapter.id) if chapter.id is not None else "",
            str(chapter.chapter_order) if chapter.chapter_order is not None else "",
            chapter.source_chapter_id or "",
        }
        if normalized in candidates:
            return chapter
    return None


def _download_status_label(state: str) -> str:
    labels = {
        "not_started": "未开始",
        "partial": "部分下载",
        "complete": "已完成",
        "empty": "空目录",
    }
    return labels.get(state, state)
