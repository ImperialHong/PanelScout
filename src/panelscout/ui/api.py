"""Local UI API services for the PanelScout runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from panelscout.adapters.zaimanhua import SOURCE_NAME, build_robots_url
from panelscout.auth import (
    CHAPTER_IMAGE_RENDER_SELECTOR,
    AuthenticatedBrowserHtmlFetcher,
    AuthSessionError,
)
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
from panelscout.storage.models import AuthSession, Chapter, Comic
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
        source = str(payload.get("source") or self.config.source)
        factory = _search_fetcher_factory_for_payload(
            payload,
            self.config,
            source,
            self.factories.search_fetcher_factory,
        )
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
        except (
            RobotsLoadError,
            RobotsDisallowedError,
            FetchError,
            AuthSessionError,
        ) as error:
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
        source = str(payload.get("source") or self.config.source)
        try:
            normalize_detail_reference(reference)
        except ValueError as error:
            raise UiApiError(str(error), status_code=400) from error

        factory = _sync_fetcher_factory_for_payload(
            payload,
            self.config,
            source,
            self.factories.sync_fetcher_factory,
        )
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
        except (
            RobotsLoadError,
            RobotsDisallowedError,
            FetchError,
            AuthSessionError,
        ) as error:
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
        factory = _download_fetcher_factory_for_payload(
            payload,
            self.config,
            source,
            self.factories.download_fetcher_factory,
        )
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
        except (
            RobotsLoadError,
            RobotsDisallowedError,
            FetchError,
            AuthSessionError,
        ) as error:
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
        download_factory = _download_fetcher_factory_for_payload(
            payload,
            self.config,
            source,
            self.factories.download_fetcher_factory,
        )
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
        except (
            RobotsLoadError,
            RobotsDisallowedError,
            FetchError,
            AuthSessionError,
        ) as error:
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


def _create_authenticated_html_fetcher(
    config: PanelScoutConfig,
    session: AuthSession,
    *,
    render_ready_selector: str | None = None,
    render_wait_seconds: float | None = None,
    render_scroll_to_bottom: bool = False,
    render_scroll_min_rounds: int = 0,
    render_image_snapshot: bool = False,
    render_click_texts: tuple[str, ...] = (),
) -> AuthenticatedBrowserHtmlFetcher:
    if not session.session_path:
        raise AuthSessionError("auth session metadata has no session file path")
    robots_policy = load_robots_policy(
        build_robots_url(),
        user_agent=config.user_agent,
    )
    fetcher_options: dict[str, Any] = {}
    if render_ready_selector is not None:
        fetcher_options["render_ready_selector"] = render_ready_selector
    if render_wait_seconds is not None:
        fetcher_options["render_wait_seconds"] = render_wait_seconds
    if render_scroll_to_bottom:
        fetcher_options["render_scroll_to_bottom"] = True
    if render_scroll_min_rounds:
        fetcher_options["render_scroll_min_rounds"] = render_scroll_min_rounds
    if render_image_snapshot:
        fetcher_options["render_image_snapshot"] = True
    if render_click_texts:
        fetcher_options["render_click_texts"] = render_click_texts
    return AuthenticatedBrowserHtmlFetcher(
        config=config,
        session_path=session.session_path,
        robots_policy=robots_policy,
        **fetcher_options,
    )


def _create_authenticated_search_fetcher(
    config: PanelScoutConfig,
    session: AuthSession,
) -> AuthenticatedBrowserHtmlFetcher:
    return _create_authenticated_html_fetcher(
        config,
        session,
        render_ready_selector='a[href*="/details/"]',
        render_wait_seconds=10,
    )


def _create_authenticated_sync_fetcher(
    config: PanelScoutConfig,
    session: AuthSession,
) -> AuthenticatedBrowserHtmlFetcher:
    return _create_authenticated_html_fetcher(config, session)


def _create_authenticated_download_fetcher(
    config: PanelScoutConfig,
    session: AuthSession,
) -> AuthenticatedBrowserHtmlFetcher:
    return _create_authenticated_html_fetcher(
        config,
        session,
        render_ready_selector=CHAPTER_IMAGE_RENDER_SELECTOR,
        render_wait_seconds=10,
        render_click_texts=("滚动阅读",),
        render_scroll_to_bottom=True,
        render_scroll_min_rounds=20,
        render_image_snapshot=True,
    )


def _create_image_fetcher(config: PanelScoutConfig) -> ImageFetcher:
    return ImageFetcher(config=config)


def _search_fetcher_factory_for_payload(
    payload: dict[str, Any],
    config: PanelScoutConfig,
    source: str,
    injected_factory: FetcherFactory | None,
) -> FetcherFactory:
    session = _auth_session_from_payload(payload, config, source, action="search")
    if session is None:
        return injected_factory or _create_html_fetcher
    if injected_factory is not None:
        return injected_factory
    return lambda runtime_config: _create_authenticated_search_fetcher(
        runtime_config,
        session,
    )


def _sync_fetcher_factory_for_payload(
    payload: dict[str, Any],
    config: PanelScoutConfig,
    source: str,
    injected_factory: FetcherFactory | None,
) -> FetcherFactory:
    session = _auth_session_from_payload(payload, config, source, action="sync")
    if session is None:
        return injected_factory or _create_html_fetcher
    if injected_factory is not None:
        return injected_factory
    return lambda runtime_config: _create_authenticated_sync_fetcher(
        runtime_config,
        session,
    )


def _download_fetcher_factory_for_payload(
    payload: dict[str, Any],
    config: PanelScoutConfig,
    source: str,
    injected_factory: FetcherFactory | None,
) -> FetcherFactory:
    session = _auth_session_from_payload(payload, config, source, action="download")
    if session is None:
        return injected_factory or _create_html_fetcher
    if injected_factory is not None:
        return injected_factory
    return lambda runtime_config: _create_authenticated_download_fetcher(
        runtime_config,
        session,
    )


def _auth_session_from_payload(
    payload: dict[str, Any],
    config: PanelScoutConfig,
    source: str,
    *,
    action: str,
) -> AuthSession | None:
    auth_source = _auth_source_from_payload(payload, source)
    if auth_source is None:
        return None
    if auth_source != source:
        raise UiApiError(
            f"{action} auth source '{auth_source}' does not match source '{source}'",
            status_code=400,
        )
    if auth_source != SOURCE_NAME:
        raise UiApiError(f"unsupported auth source: {auth_source}", status_code=400)
    return _require_auth_session(config, auth_source)


def _auth_source_from_payload(payload: dict[str, Any], source: str) -> str | None:
    raw_auth = payload.get("auth", False)
    if raw_auth is False or raw_auth is None:
        return None
    if raw_auth is True:
        return source
    auth_text = str(raw_auth).strip()
    if auth_text.lower() in {"", "0", "false", "no", "off"}:
        return None
    return auth_text


def _require_auth_session(config: PanelScoutConfig, source: str) -> AuthSession:
    if str(config.database_path) != ":memory:":
        database_path = Path(config.database_path).expanduser()
        if not database_path.exists():
            raise UiApiError(
                "auth session not configured; run auth login first",
                status_code=401,
            )

    with connect_database(config.database_path) as connection:
        session = ComicRepository(connection).get_auth_session(source)

    if session is None:
        raise UiApiError(
            "auth session not configured; run auth login first",
            status_code=401,
        )
    if not session.session_path:
        raise UiApiError(
            "auth session metadata has no session file path",
            status_code=401,
        )
    session_file = Path(session.session_path).expanduser()
    if not session_file.exists():
        raise UiApiError(f"auth session file missing: {session_file}", status_code=401)
    return session


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
