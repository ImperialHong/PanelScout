# PanelScout Unit Acceptance Reports

Date: 2026-07-20

This file contains the Unit-level implementation and validation reports for PanelScout. The design document links here instead of carrying detailed Unit acceptance logs inline.

Related design document: [PanelScout Design Document](design-document.md).

## Unit Acceptance Reports

### Unit 1: Project Skeleton and CLI Baseline

Status: accepted

Validation owner: Agent2

Accepted on: 2026-07-20

Implemented files:

- `.gitignore`
- `pyproject.toml`
- `src/panelscout/__init__.py`
- `src/panelscout/cli.py`
- `src/panelscout/config.py`
- placeholder package directories under `src/panelscout/`
- `tests/test_cli.py`
- `tests/test_config.py`

Validation summary:

- `compileall` passed for `src` and `tests`.
- `unittest discover` passed with 8 tests.
- CLI help, version, config display, and placeholder search commands passed.
- No network, crawler, login, or downloader behavior was introduced.
- Python 3.12+ is required by the project. The host default `python3` may be older, so local checks should use a Python 3.12+ interpreter.

### Unit 2: SQLite Storage Baseline

Status: accepted

Validation owner: Agent2

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/storage/__init__.py`
- `src/panelscout/storage/database.py`
- `src/panelscout/storage/models.py`
- `src/panelscout/storage/repositories.py`
- `tests/test_storage.py`

Validation summary:

- SQLite schema initialization covers `comics`, `chapters`, `crawl_jobs`, `crawl_logs`, and `auth_sessions`.
- Foreign keys are enabled and validated.
- Schema initialization is idempotent.
- Repository helpers support comic upsert, chapter upsert, stored comic listing, and stored comic search.
- Storage tests use temporary or in-memory databases and do not write to user home.
- `unittest discover` passed with 13 tests.
- `compileall` passed for `src` and `tests`.
- No network, crawler, login, or downloader behavior was introduced.

### Unit 3: Exporter Baseline

Status: accepted

Validation owner: Agent2

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/cli.py`
- `src/panelscout/exporters/__init__.py`
- `src/panelscout/exporters/_records.py`
- `src/panelscout/exporters/json_exporter.py`
- `src/panelscout/exporters/csv_exporter.py`
- `src/panelscout/exporters/markdown_exporter.py`
- `tests/test_exporters.py`

Validation summary:

- JSON, CSV, and Markdown exports work from stored comic metadata.
- Export output is deterministic enough for tests and preserves tuple fields such as categories and tags.
- `panelscout export --format json|csv|markdown` can export from an explicitly configured SQLite database.
- Default export with a missing database returns an empty result without creating user-home database directories.
- `unittest discover` passed with 20 tests.
- `compileall` passed for `src` and `tests`.
- No network, crawler, parser, login, or downloader behavior was introduced.

### Unit 4: Anonymous Metadata Parser Fixtures and Parser

Status: accepted

Validation owner: Agent2

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/adapters/zaimanhua.py`
- `src/panelscout/parsers/__init__.py`
- `src/panelscout/parsers/zaimanhua.py`
- `tests/test_zaimanhua_parser.py`
- `tests/fixtures/zaimanhua/search_weisample.html`
- `tests/fixtures/zaimanhua/details_15599.html`
- `tests/fixtures/zaimanhua/robots.txt`

Validation summary:

- Search/list parsing extracts public metadata into `Comic` records.
- Known public fixture record validated: `伪恋同盟`, source comic id `15599`, author `榊葵/绫乃`, latest chapter `第112话`.
- Detail-page parsing extracts SEO metadata and returns an empty chapter list for the current unavailable/down fixture.
- URL helpers build search/detail URLs and normalize public source URLs.
- Fixtures are compact and local-only; no cookies, credentials, or large raw Nuxt dumps are committed.
- Unit 4 parser tests passed with 3 tests.
- Full `unittest discover` passed with 23 tests.
- `compileall` passed for `src` and `tests`.
- No network, fetcher, crawler, login, or downloader behavior was introduced.

### Unit 5: Robots Policy and Fetcher Baseline

Status: accepted

Validation owner: Agent2

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/crawler/__init__.py`
- `src/panelscout/crawler/robots.py`
- `src/panelscout/crawler/fetcher.py`
- `tests/test_robots.py`
- `tests/test_fetcher.py`

Validation summary:

- Local robots policy parser allows `/dynamic/` and `/details/`.
- Local robots policy parser disallows `/api/`, `/dingyue/`, and matching blocked static paths such as `/_nuxt/*.js`.
- `Crawl-delay: 1` is parsed from the ZaiManHua robots fixture.
- Fetcher uses an injectable opener, sleeper, and clock for no-network tests.
- Fetcher applies the configured PanelScout User-Agent.
- Fetcher checks robots before opening a URL.
- Fetcher rejects blocked statuses and non-HTML content types.
- CLI `search` remains a placeholder and is not wired to live fetching yet.
- Unit 5 focused tests passed with 11 tests.
- Full `unittest discover` passed with 34 tests.
- `compileall` passed for `src` and `tests`.
- No live network, login, browser, downloader, or crawler workflow behavior was introduced.

Future note:

- When robots loading is added, unknown or unavailable robots state should fail closed or require an explicit user-visible override for local development.

### Unit 6: Public Search Workflow Service

Status: accepted

Validation owner: Agent2

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/crawler/__init__.py`
- `src/panelscout/crawler/engine.py`
- `tests/test_search_workflow.py`

Validation summary:

- Search workflow accepts a query and an injected fetcher-like object.
- Search workflow builds the encoded ZaiManHua `/dynamic/{query}` URL.
- Search workflow parses fixture HTML through the Unit 4 parser.
- Known public fixture record validated: `伪恋同盟`, source comic id `15599`, author `榊葵/绫乃`, latest chapter `第112话`.
- Optional repository persistence upserts parsed comics into an in-memory SQLite database.
- Blank queries are rejected before any fetcher call.
- CLI `search` remains a no-network placeholder.
- Unit 6 focused tests passed with 3 tests.
- Full `unittest discover` passed with 37 tests.
- `compileall` passed for `src` and `tests`.
- No live network, login, browser, downloader, or CLI live search behavior was introduced.

### Unit 7: Safe CLI Search Integration

Status: accepted

Validation owner: Agent2

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/cli.py`
- `src/panelscout/adapters/zaimanhua.py`
- `src/panelscout/crawler/__init__.py`
- `src/panelscout/crawler/robots.py`
- `tests/test_cli.py`
- `tests/test_robots.py`

Validation summary:

- `panelscout search QUERY` is wired to the public search workflow.
- Search uses a robots-aware `HtmlFetcher`.
- Default search prints parsed results and does not persist data.
- Default search does not create user-home database directories.
- `panelscout search QUERY --save` persists results only to the configured SQLite database.
- Blank search queries are rejected before fetcher creation.
- Robots loading failure fails closed with a clear non-zero CLI result.
- Tests use injected fake fetchers and local fixtures only.
- Unit 7 focused CLI and robots tests passed with 14 tests.
- Full `unittest discover` passed with 42 tests.
- `compileall` passed for `src` and `tests`.
- No auth, browser, downloader, detail sync, or chapter crawling behavior was introduced.

### Unit 8: Public Detail Sync Workflow Baseline

Status: accepted

Validation owner: Agent2

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/crawler/__init__.py`
- `src/panelscout/crawler/engine.py`
- `src/panelscout/parsers/zaimanhua.py`
- `tests/test_detail_sync_workflow.py`
- `tests/fixtures/zaimanhua/details_15599_with_chapters.html`

Validation summary:

- `sync_public_detail` accepts a source comic id, relative details path, or public ZaiManHua details URL.
- Detail references are normalized to canonical public details URLs.
- The workflow requires an injected fetcher and does not instantiate a live network client.
- The workflow parses public detail metadata through the existing detail parser.
- The workflow upserts the comic into SQLite through `ComicRepository`.
- The workflow upserts visible parsed chapters and avoids duplicate chapter records.
- `new_chapter_count` reports newly observed chapters and is idempotent on repeat sync.
- Invalid references are rejected before any fetcher call.
- `panelscout sync` remains a no-network placeholder.
- Unit 8 focused tests passed with 3 tests.
- Full `unittest discover` passed with 45 tests.
- `compileall` passed for `src` and `tests`.
- No live network, auth, browser, downloader, or CLI live sync behavior was introduced.

### Unit 9: Safe CLI Sync Integration

Status: accepted

Validation owner: Agent2

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/cli.py`
- `src/panelscout/crawler/__init__.py`
- `src/panelscout/crawler/engine.py`
- `tests/test_cli.py`

Validation summary:

- `panelscout sync REF` is wired to public/anonymous detail sync.
- `REF` may be a source comic id, relative details path, or public ZaiManHua details URL.
- Default `sync` is a dry-run using in-memory SQLite and does not create user-home database directories.
- `panelscout sync REF --save` persists detail metadata and visible chapters to the configured SQLite database.
- Saved sync is idempotent: repeated sync does not duplicate comic or chapter records.
- Blank and invalid references are rejected before fetcher creation.
- Robots loading failure fails closed with a clear non-zero CLI result.
- Tests use injected fake fetchers and local fixtures only.
- CLI focused tests passed with 11 tests.
- Full `unittest discover` passed with 49 tests.
- `compileall` passed for `src` and `tests`.
- No live network, auth, browser, downloader, or image/content crawling behavior was introduced.

### Unit 10: Richer Sync Result and Report Output

Status: accepted

Validation owner: Agent2

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/cli.py`
- `src/panelscout/crawler/__init__.py`
- `src/panelscout/crawler/engine.py`
- `tests/test_cli.py`
- `tests/test_detail_sync_workflow.py`
- `tests/fixtures/zaimanhua/details_15599_updated_with_chapters.html`

Validation summary:

- `PublicDetailSyncResult` now returns explicit `new_chapters`, `new_chapter_count`, and `existing_chapter_count`.
- Public detail sync reports metadata changes for `title`, `author`, `status`, and `latest_chapter_title` only.
- `last_checked_at` is refreshed on sync but is not treated as a user-facing metadata change.
- CLI `sync` output now separates total chapters, new chapters, existing chapters, metadata changes, and new chapter details.
- Fixture-driven idempotency tests cover first sync, changed detail sync with one new chapter, and repeated unchanged sync.
- Dry-run sync still uses in-memory SQLite and does not create user-home paths.
- `--save` persists only to the configured test database in CLI coverage.
- Focused workflow and CLI tests passed; full `unittest discover` passed with 51 tests.
- `compileall` passed for `src` and `tests`.
- `git diff --check` passed.
- No live network, auth, browser, downloader, session, cookie, or image/content crawling behavior was introduced.

### Unit 11: Local Watchlist Baseline

Status: accepted

Validation owner: Agent2

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/cli.py`
- `src/panelscout/storage/__init__.py`
- `src/panelscout/storage/database.py`
- `src/panelscout/storage/models.py`
- `src/panelscout/storage/repositories.py`
- `tests/test_cli.py`
- `tests/test_storage.py`

Validation summary:

- SQLite schema now includes `watchlist_entries` with a unique comic membership and `ON DELETE CASCADE`.
- `WatchlistEntry` models local watchlist membership joined with comic metadata.
- `ComicRepository` now supports adding, removing, loading, and listing watchlist entries.
- Watchlist add only accepts comics already saved in the local catalog and performs no network fetch.
- Duplicate watchlist add is idempotent and does not create duplicate rows.
- CLI supports `panelscout watch list`, `panelscout watch add SOURCE_COMIC_ID`, and `panelscout watch remove SOURCE_COMIC_ID`.
- Watchlist CLI commands use the configured SQLite database and provide clear empty, missing, and unsupported-source behavior.
- Storage tests cover schema creation, add/list/remove, duplicate add, missing comic rejection, deterministic ordering, and cascade delete.
- CLI tests cover add/list/remove, duplicate add, missing local catalog comic, removing an unwatched local comic, blank references, and unsupported sources.
- Full `unittest discover` passed with 59 tests.
- `compileall` passed for `src` and `tests`.
- `git diff --check` passed.
- No scheduler, update report generation, live network, auth, browser, downloader, session, cookie, or image/content crawling behavior was introduced.

### Unit 12: Watchlist Update Check Baseline

Status: accepted

Validation owner: Agent2

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/cli.py`
- `src/panelscout/crawler/__init__.py`
- `src/panelscout/crawler/engine.py`
- `src/panelscout/storage/repositories.py`
- `tests/test_cli.py`
- `tests/test_detail_sync_workflow.py`
- `tests/test_storage.py`

Validation summary:

- `check_watchlist_public_updates` reads watched comics from the configured SQLite database.
- Watchlist checks reuse public/anonymous `sync_public_detail` and do not authenticate, run browsers, or download content.
- CLI supports `panelscout watch check` and `panelscout watch check --limit N`.
- Watch checks persist refreshed detail metadata, visible chapters, new chapter counts, and metadata changes.
- Empty watchlists return a clear success result without fetching.
- One failed watched comic does not abort the rest of the batch.
- Watchlist `last_checked_at` is updated after success or per-item failure.
- Tests use fake fetchers and local fixtures only.

### Unit 13: Markdown Watch Check Report

Status: accepted

Validation owner: Agent2

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/cli.py`
- `src/panelscout/exporters/__init__.py`
- `src/panelscout/exporters/markdown_exporter.py`
- `tests/test_cli.py`
- `tests/test_exporters.py`

Validation summary:

- `export_watch_check_markdown` renders a local Markdown report for one watch check result.
- Reports include summary counts, per-comic status, new chapter links, metadata changes, and failures.
- CLI supports `panelscout watch check --report PATH` to write a local Markdown report.
- Report generation does not create network, scheduler, auth, browser, downloader, session, cookie, or image/content crawling behavior.

### Unit 14: Local Watch Check Schedule Baseline

Status: accepted

Validation owner: Agent2

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/cli.py`
- `src/panelscout/storage/__init__.py`
- `src/panelscout/storage/database.py`
- `src/panelscout/storage/models.py`
- `src/panelscout/storage/repositories.py`
- `tests/test_cli.py`
- `tests/test_storage.py`

Validation summary:

- SQLite schema now includes `watch_check_schedules`.
- `WatchCheckSchedule` models local suggested watch check timing.
- Repository helpers can set, show, clear, list due schedules, and mark a manual run.
- CLI supports `panelscout watch schedule set/show/due/clear`.
- Schedule support is local state only; it does not start a background daemon, thread, subprocess, APScheduler runtime, or automatic network work.
- Full `unittest discover` passed with 71 tests.
- `compileall` passed for `src` and `tests`.
- `git diff --check` passed.
- Agent2 full MVP3 validation passed.
- No live network, auth, browser, downloader, session, cookie, background daemon, or image/content crawling behavior was introduced.

### Unit 15: Local UI Shell Baseline

Status: accepted

Validation owner: Agent2

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/cli.py`
- `src/panelscout/ui/__init__.py`
- `src/panelscout/ui/shell.py`
- `tests/test_cli.py`
- `tests/test_ui.py`

Validation summary:

- `panelscout ui build --output PATH` writes a static local HTML shell.
- The UI shell includes the MVP 4 navigation and sections: Search, Local Library, Watchlist, Update History, Downloads, and Settings.
- Static UI areas include a search toolbar, result/library pane, comic detail pane, watchlist status, update history/report area, chapter selector, download queue tabs, folder preview, and settings controls.
- Download folder preview follows `download_root/漫画名/001话/001.jpg`, matching the planned `漫画名/章节名/001.ext` layout.
- Download execution controls are visible only as planned/disabled controls.
- Unit 15 does not introduce live network, auth/login/session/cookie workflow, browser automation, downloader engine, image fetching, background daemon, or scheduler behavior.
- Focused `tests.test_ui` and `tests.test_cli` checks passed with 28 tests.
- Full `unittest discover` passed with 76 tests.
- `compileall` passed for `src` and `tests`.
- `git diff --check` passed.
- Agent2 validation passed.

### Unit 16: Local UI Data Binding Baseline

Status: accepted

Validation owner: Agent2

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/cli.py`
- `src/panelscout/ui/__init__.py`
- `src/panelscout/ui/shell.py`
- `src/panelscout/ui/state.py`
- `tests/test_cli.py`
- `tests/test_ui.py`

Validation summary:

- `panelscout ui build --output PATH` now builds a local UI state snapshot from the configured SQLite database when the database exists.
- The static UI renders real local catalog entries, selected comic metadata, selected comic local chapters, watchlist entries, watchlist notes, watch checked-status, watch schedule summary, and database path.
- Missing databases render safe empty states and do not create default user-home database directories.
- Initialized empty databases render explicit empty states and do not fall back to sample data.
- The Downloads chapter selector is populated from the selected comic's local chapters when available.
- Download controls remain visible only as planned/disabled controls; no downloader engine, image fetching, retry execution, or queue runtime was introduced.
- Unit 16 does not introduce live network, auth/login/session/cookie workflow, browser automation, background daemon, scheduler execution, or image/content crawling behavior.
- Focused `tests.test_ui` and `tests.test_cli` checks passed with 32 tests.
- Full `unittest discover` passed with 80 tests.
- `compileall` passed for `src` and `tests`.
- `git diff --check` passed.
- Agent2 validation passed after the initialized-empty database test coverage was added.

### Unit 17: Chinese Local UI Copy Baseline

Status: accepted

Validation owner: Agent2

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/cli.py`
- `src/panelscout/ui/shell.py`
- `src/panelscout/ui/state.py`
- `tests/test_cli.py`
- `tests/test_ui.py`

Validation summary:

- The static local UI now uses Simplified Chinese for user-visible navigation, headings, table headers, buttons, statuses, empty states, download copy, settings copy, update-history copy, and watchlist copy.
- The HTML document language is `zh-CN`, and core accessibility labels are Chinese.
- Stable section anchors remain `search`, `local-library`, `watchlist`, `update-history`, `downloads`, and `settings`.
- `panelscout ui build --output PATH` keeps the same command shape, but UI-related output is Chinese and still states that no service, network, login, or download task was started.
- Data-backed rendering for comics, authors, latest chapters, detail URLs, chapters, watchlist notes, and download folder previews still works.
- Missing and initialized-empty database states render Chinese empty-state copy and do not create default user-home database directories.
- Download controls remain disabled and planning-only; no downloader engine, image fetching, retry execution, or queue runtime was introduced.
- Focused `tests.test_ui` and `tests.test_cli` checks passed with 32 tests.
- Full `unittest discover` passed with 80 tests.
- `compileall` passed for `src` and `tests`.
- `git diff --check` passed.
- Generated HTML scan found no old English UI copy such as `Search`, `Local Library`, `Watchlist`, `Download selected chapters - planned`, or `Retry failed - planned`.
- Agent2 validation passed.

### Unit 18: Downloader Planner Baseline

Status: accepted

Validation owner: Codex main

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/downloader/__init__.py`
- `src/panelscout/downloader/planner.py`
- `tests/test_downloader_planner.py`

Validation summary:

- Added pure downloader planning models for image candidates, plan items, and chapter download plans.
- `build_download_plan` creates local target paths using `download_root/comic_title/chapter_title/page_number.ext`.
- Comic and chapter path segments are filename-safe and fall back safely when the title is empty or only invalid path characters.
- Image extension inference preserves known extensions from explicit metadata or source URLs without fetching images.
- Duplicate planned filenames receive stable numeric suffixes.
- Existing complete files plan as `skip_existing`; existing `.part` files plan as `resume_partial`; missing files plan as `download`.
- Download plans require a nonblank permission note for future local auditability.
- The planner does not create directories, write files, fetch pages, fetch images, authenticate, run browsers, or start background work.
- Focused `tests.test_downloader_planner` checks passed with 5 tests.
- Full `unittest discover` passed with 85 tests.
- `compileall` passed for `src` and `tests`.
- `git diff --check` passed.

### Unit 19: Public Chapter Image Discovery Fixtures and Parser

Status: accepted

Validation owner: Codex main

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/downloader/__init__.py`
- `src/panelscout/downloader/discovery.py`
- `tests/fixtures/zaimanhua/chapter_15599_1001.html`
- `tests/test_chapter_image_discovery.py`

Validation summary:

- Added fixture-backed public chapter image discovery for saved/fetched chapter HTML.
- Parser extracts image URLs from `img` and `source` attributes, `srcset`-style fields, and supported JSON/script URL markers.
- Relative and protocol-relative image URLs normalize against the source chapter URL.
- Non-image resources such as SVG markup are ignored, image extensions are normalized, and duplicate URLs are deduped.
- The parser is pure string parsing: it does not fetch pages, evaluate JavaScript, authenticate, use cookies, run a browser, or download image bytes.
- Focused discovery tests passed with 2 tests.

### Unit 20: Opt-In CLI Download Dry-Run

Status: accepted

Validation owner: Codex main

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/cli.py`
- `src/panelscout/downloader/workflow.py`
- `tests/test_cli.py`
- `tests/test_download_workflow.py`

Validation summary:

- Added `panelscout download plan SOURCE_COMIC_ID --chapter REF --output-root PATH --permission-note NOTE`.
- The command loads an existing saved comic and local chapter from the configured SQLite database.
- Chapter references may match chapter title, URL, local id, source chapter id, or chapter order.
- The command fetches chapter HTML through the existing robots-aware HTML fetcher path, discovers public image candidates, and prints planned local file paths.
- Dry-run planning does not create the download root, write image files, fetch image bytes, authenticate, use cookies, run a browser, or start background work.
- Missing default local databases fail cleanly without creating user-home config/data/cache directories.

### Unit 21: Opt-In CLI Image Save Baseline

Status: accepted

Validation owner: Codex main

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/cli.py`
- `src/panelscout/downloader/__init__.py`
- `src/panelscout/downloader/fetcher.py`
- `src/panelscout/downloader/workflow.py`
- `tests/test_cli.py`
- `tests/test_download_workflow.py`

Validation summary:

- Added `panelscout download run SOURCE_COMIC_ID --chapter REF --output-root PATH --permission-note NOTE`.
- The save workflow reuses the accepted download plan and writes to `download_root/漫画名/章节名/001.ext`.
- Images are fetched only after explicit command invocation and a nonblank permission note.
- Image responses are saved through `.part` temporary files and atomically renamed after complete bytes are available.
- Existing completed files are skipped, existing partial files are planned as resumable/download work, and independent page failures do not create complete target files.
- The image fetcher sends a clear User-Agent and generic image Accept header only. It does not add credentials, cookies, sessions, referer spoofing, browser automation, anti-hotlinking bypass, or queue/background behavior.
- Blocked or non-image responses fail with clear local errors.

### Unit 22: End-to-End Minimum Line Validation

Status: accepted

Validation owner: Codex main

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/cli.py`
- `src/panelscout/downloader/discovery.py`
- `src/panelscout/downloader/fetcher.py`
- `src/panelscout/downloader/planner.py`
- `src/panelscout/downloader/workflow.py`
- `tests/fixtures/zaimanhua/chapter_15599_1001.html`
- `tests/test_chapter_image_discovery.py`
- `tests/test_download_workflow.py`
- `tests/test_cli.py`

Validation summary:

- Fixture-backed tests validate the minimum business line: public search -> save comic -> public detail/chapter sync -> select chapter -> plan/save selected chapter images.
- The expected local output layout is created as `downloads/伪恋同盟/第001话 背叛之后/001.jpg`, `002.png`, `003.png`, and `004.webp`.
- CLI tests cover download planning without file writes, explicit download saving, and missing database failure without default directory creation.
- Focused Unit 19-22 tests passed with 35 tests.
- Full `unittest discover` passed with 94 tests.
- `compileall` passed for `src` and `tests`.
- `git diff --check` passed.
- Boundary scan found only expected negative/fixture references for session paths, authorization wording, and no-login/no-bypass comments; no executable login/auth/session/cookie/browser/background queue behavior was added.
- No login/auth/session/cookie workflow, browser automation, paid/VIP bypass, referer spoofing, source restriction bypass, or background queue was introduced.

### Unit 23: UI Download Command Bridge and `/downloads` Default

Status: accepted

Validation owner: Codex main

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/config.py`
- `src/panelscout/cli.py`
- `src/panelscout/ui/state.py`
- `src/panelscout/ui/shell.py`
- `src/panelscout/downloader/workflow.py`
- `tests/test_config.py`
- `tests/test_ui.py`
- `tests/test_cli.py`
- `tests/test_download_workflow.py`

Validation summary:

- `PanelScoutConfig.download_root` now defaults to `/downloads`.
- Config supports `[paths] download_root = "/custom/path"` overrides.
- `panelscout download plan/run` can omit `--output-root` and will use the configured `download_root`.
- The Chinese static UI renders `/downloads` in the settings field, folder preview, and copyable `panelscout download plan/run` command previews for the selected local chapter.
- The static UI still does not execute downloads, start a server, run browser automation, create sessions/cookies, or start background queues.
- Download workflow now fails cleanly when the target chapter directory cannot be created.
- `/downloads` smoke test was attempted with fixture HTML and fake image bytes. On this macOS host, `/downloads` does not exist and root is read-only, so the smoke test returned `saved=0 skipped=0 failed=4` without a Python traceback.
- Control smoke test to `/private/tmp/panelscout-downloads` saved 4 fixture image files as `001.jpg`, `002.png`, `003.png`, and `004.webp`, confirming the save path works when the target root is writable.
- Focused config/UI/CLI/download workflow tests passed with 46 tests.
- Full `unittest discover` passed with 97 tests.
- `compileall` passed for `src` and `tests`.
- `git diff --check` passed.
- Boundary scan found only expected author-field matches, fixture/config `session_dir` references, and negative no-login/no-bypass/no-background wording.
- No login/auth/session/cookie workflow, browser automation, paid/VIP bypass, referer spoofing, source restriction bypass, or background queue was introduced.

### Unit 24: macOS Downloads Default and Smoke Test

Status: accepted

Validation owner: Codex main

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/config.py`
- `src/panelscout/ui/state.py`
- `src/panelscout/ui/shell.py`
- `tests/test_config.py`
- `tests/test_ui.py`
- `tests/test_cli.py`
- `docs/design-document.md`

Validation summary:

- Changed the default configured `download_root` from `/downloads` to the macOS default Downloads folder, `~/Downloads`.
- Runtime config expands the default to the current user's Downloads directory, for example `/Users/jay/Downloads`.
- The Chinese static UI now renders the macOS Downloads default in the settings field, folder preview, and command previews.
- `panelscout download plan/run` still accepts explicit `--output-root`, and when omitted uses the configured default.
- CLI smoke test omitted `--output-root` and used fixture HTML plus fake image bytes; it saved 4 files to `/Users/jay/Downloads/PanelScout下载测试/第001话 测试下载 20260720225638/`.
- Smoke test output files: `001.jpg`, `002.png`, `003.png`, and `004.webp`.
- Focused config/UI/CLI tests passed with 41 tests.
- Full `unittest discover` passed with 97 tests.
- `compileall` passed for `src` and `tests`.
- `git diff --check` passed.
- Boundary scan found only expected historical `/downloads` Unit 23 notes, author-field matches, fixture/config `session_dir` references, and negative no-login/no-bypass/no-background wording.
- No live network, real source image downloads, login/auth/session/cookie workflow, browser automation, paid/VIP bypass, referer spoofing, source restriction bypass, or background queue was introduced.

### Unit 25: UI Download Status Import

Status: accepted

Validation owner: Agent2 and Codex main

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/downloader/__init__.py`
- `src/panelscout/downloader/status.py`
- `src/panelscout/ui/api.py`
- `tests/test_ui_api.py`

Validation summary:

- Added reusable local download status reading for the accepted folder layout: `download_root/漫画名/章节名/001.ext`.
- Status reads distinguish `not_started`, `empty`, `partial`, and `complete` without fetching chapter HTML or image bytes.
- Complete image files and `.part` files are counted separately and returned with Chinese UI labels.
- The status reader uses the same filename-safe comic/chapter path rules as the downloader planner.
- Fixture tests cover complete and partial status reads from temporary directories.
- No live network, browser automation, login/auth/session/cookie workflow, referer spoofing, bypass behavior, or background queue was introduced.

### Unit 26: Local UI Runner/API

Status: accepted

Validation owner: Agent2 and Codex main

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/cli.py`
- `src/panelscout/ui/__init__.py`
- `src/panelscout/ui/api.py`
- `src/panelscout/ui/app_shell.py`
- `src/panelscout/ui/server.py`
- `tests/test_cli.py`
- `tests/test_ui_api.py`
- `tests/test_ui_runner.py`

Validation summary:

- Added `panelscout ui serve`, a foreground local HTTP runner for the interactive Chinese UI.
- The runner binds only to `127.0.0.1` and rejects public host values such as `0.0.0.0` before binding.
- The HTTP app is directly testable without opening a socket.
- JSON errors are returned with clear local messages for invalid JSON, blank inputs, missing local database, and unsupported routes.
- The runner uses direct PanelScout workflow calls, not shell subprocess calls to the CLI.
- The runner does not start automatically from `ui build`, does not run as a daemon, and does not create a queue/threading scheduler.

### Unit 27: UI Search/Save and Detail Sync Bridge

Status: accepted

Validation owner: Agent2 and Codex main

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/ui/api.py`
- `src/panelscout/ui/app_shell.py`
- `tests/test_ui_api.py`
- `tests/test_ui_runner.py`

Validation summary:

- Added local API methods and UI actions for public search/save and public detail/chapter sync.
- The interactive UI exposes Chinese controls for search, local library selection, source comic id, and detail sync.
- UI JavaScript calls only local runner endpoints such as `/api/search`, `/api/sync`, and `/api/state`; it does not call third-party websites directly from the browser.
- Search and sync use the existing robots-aware fetcher path by default and fixture fetchers in tests.
- Saved search/sync results refresh local UI state from SQLite.
- Dynamic site data is rendered with DOM text nodes instead of raw HTML injection.

### Unit 28: UI Download Plan/Run Bridge

Status: accepted

Validation owner: Agent2 and Codex main

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/ui/api.py`
- `src/panelscout/ui/app_shell.py`
- `tests/test_ui_api.py`
- `tests/test_ui_runner.py`

Validation summary:

- Added local API methods and UI actions for explicit `download plan` and `download run` behavior.
- The interactive UI sends the selected saved comic, selected chapter, output root, and permission note to local endpoints only.
- Download planning previews the accepted folder layout without fetching image bytes.
- Download running reuses the accepted downloader workflow, writes through `.part` files, and returns saved/skipped/failed item results.
- Permission note remains required before planning or running a download.
- Fixture tests cover the UI API line through saved output files `001.jpg`, `002.png`, `003.png`, and `004.webp`.

### Unit 29: UI Download Status Readout

Status: accepted

Validation owner: Agent2 and Codex main

Accepted on: 2026-07-20

Implemented files:

- `src/panelscout/ui/api.py`
- `src/panelscout/ui/app_shell.py`
- `src/panelscout/ui/server.py`
- `tests/test_ui_api.py`
- `tests/test_ui_runner.py`

Validation summary:

- Added `/api/download/status` and a Chinese UI status action for the selected local chapter.
- Download status can be read after a run or independently from existing local files.
- The run response includes the latest local download status snapshot.
- Focused UI/API/CLI tests passed with 42 tests.
- Full `unittest discover` passed with 109 tests.
- `compileall` passed for `src` and `tests`.
- Boundary scan found only expected matches: public-host rejection tests, foreground local `serve_forever`, historical design/auth/session placeholders, `session_dir` fixture paths, author-field text, and negative no-login/no-bypass/no-background wording.
- No live network, real source image downloads, login/auth/session/cookie workflow, browser automation, paid/VIP bypass, referer spoofing, source restriction bypass, public hosting, background daemon, or queue runtime was introduced.
