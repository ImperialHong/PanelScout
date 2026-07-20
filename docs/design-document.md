# PanelScout Design Document

Version: 0.14

Date: 2026-07-20

Chinese name: 格探

## 1. Project Summary

PanelScout is a local comic discovery, cataloging, and update-monitoring application. The first supported source is ZaiManHua-related public pages and user-authorized account-visible pages. The software focuses on collecting metadata, tracking chapter changes, and helping the user organize reading links.

The project must not bypass login, paywalls, CAPTCHA, anti-hotlinking, encryption, access controls, or site-imposed restrictions. Login support must use a local user-driven browser session and must not collect or store plaintext passwords. Content download is not part of the default MVP and must remain an opt-in, permission-gated module.

## 2. Goals

- Search comics by keyword, author, category, status, theme, and audience.
- Store comic metadata locally.
- Store chapter list metadata and detect new chapters.
- Provide update notifications or update reports.
- Export collected metadata to CSV, JSON, or Markdown.
- Support a local authenticated session mode for content that the user's own account can normally view.
- Keep crawling polite, rate-limited, cache-aware, and observable.

## 3. Non-Goals

- No collecting, transmitting, or storing plaintext usernames or passwords.
- No bypassing login, session expiration, CAPTCHA, or account checks.
- No accessing content unavailable to the user's own logged-in account.
- No CAPTCHA solving.
- No anti-bot evasion.
- No mass image mirroring by default.
- No redistribution or sharing workflow for copyrighted content.
- No public hosted scraping service in the first version.

## 4. Proposed Software Name

Primary name: PanelScout

Chinese name: 格探

Suggested GitHub repository name: panel-scout

Rationale: The name emphasizes discovering, tracking, and organizing comic panels and chapters. It avoids positioning the tool as a downloader.

## 5. High-Level Architecture

```text
CLI / Local Web UI
    |
Task Scheduler
    |
Crawler Engine
    |
Site Adapter: zaimanhua
    |
Fetcher -> Parser -> Storage -> Exporter
```

## 6. Core Modules

### 6.1 CLI / Local UI

Initial commands:

- `search`: Search comics by keyword or filters.
- `sync`: Crawl and refresh metadata for saved comics.
- `watch`: Check selected comics for chapter updates.
- `export`: Export metadata and update reports.

The first version can start with a CLI. A local web interface can be added after the crawler and storage layer are stable.

### 6.2 Task Scheduler

Responsibilities:

- Queue crawl jobs.
- Avoid duplicate work.
- Support scheduled update checks.
- Persist job status and errors.
- Resume interrupted jobs.

### 6.3 Crawler Engine

Responsibilities:

- Coordinate fetch, parse, and storage operations.
- Respect per-domain concurrency limits.
- Apply retry and backoff rules.
- Stop or pause on repeated `403`, `429`, or unexpected blocking responses.
- Enforce robots and policy checks before crawling.

### 6.4 Site Adapter

The first adapter is `zaimanhua`.

Responsibilities:

- Build search URLs.
- Build category/list URLs.
- Normalize detail URLs.
- Parse list cards.
- Parse search results.
- Parse comic detail metadata.
- Parse chapter list metadata.

All site-specific selectors and URL patterns should live in this adapter, not in the generic crawler engine.

### 6.5 Fetcher

Recommended behavior:

- Use a clear User-Agent identifying PanelScout.
- Default delay: 1-3 seconds between requests.
- Default concurrency: 1-2 requests per domain.
- Cache fetched HTML for development and debugging.
- Support conditional requests when possible.
- Fail closed when access rules are unclear.

### 6.6 Parser

Responsibilities:

- Parse HTML into structured records.
- Keep parser functions pure where possible.
- Handle missing fields safely.
- Preserve source URLs for traceability.
- Write parser tests using saved sample HTML fixtures.

### 6.7 Storage

Recommended initial database: SQLite.

SQLite is enough for a local single-user MVP and keeps setup simple for GitHub users.

### 6.8 Exporter

Supported first formats:

- JSON for structured backups.
- CSV for spreadsheet review.
- Markdown for readable watchlists and update reports.

### 6.9 Downloader

Downloader is a future optional module.

Rules:

- Disabled by default.
- Requires explicit user confirmation.
- Only works for content the user is authorized to archive.
- Must not bypass anti-hotlinking or restricted access.
- Must store source URL, crawl time, and permission note.

### 6.10 Authenticated Session Mode

Authenticated Session Mode allows PanelScout to access pages that are visible only after the user logs in with their own free account.

This mode must be implemented as local browser-based login, not credential collection.

Recommended command flow:

- `panelscout auth login zaimanhua`: Open a local Playwright browser window and let the user log in manually.
- `panelscout auth status zaimanhua`: Check whether a saved session still appears valid.
- `panelscout auth logout zaimanhua`: Delete the saved local session.
- `panelscout sync --auth zaimanhua`: Reuse the saved session for metadata and chapter sync.

Rules:

- The user enters credentials directly into the website in a local browser window.
- PanelScout never asks for, receives, logs, stores, or uploads plaintext credentials.
- CAPTCHA or additional verification must be solved manually by the user.
- If a session expires, PanelScout pauses and asks the user to log in again.
- Session state is saved locally as cookies and browser storage.
- Session files should be excluded from git.
- Session files should be encrypted when practical, or stored through the OS credential store.
- Authenticated crawling must still respect rate limits, robots rules where applicable, and source policy checks.
- Authenticated crawling must not expand the scope to paid, restricted, removed, or otherwise unavailable content.

Suggested local storage:

```text
~/.panelscout/sessions/zaimanhua.storage.json
```

For macOS, the preferred long-term storage is Keychain-backed session encryption. The plain JSON storage path is acceptable only for local development and must carry a warning.

## 7. Data Model

### comics

- `id`
- `source`
- `source_comic_id`
- `title`
- `author`
- `status`
- `audience`
- `categories`
- `tags`
- `summary`
- `latest_chapter_title`
- `detail_url`
- `cover_url`
- `first_seen_at`
- `last_checked_at`
- `updated_at`

### chapters

- `id`
- `comic_id`
- `source_chapter_id`
- `title`
- `chapter_order`
- `chapter_url`
- `published_hint`
- `first_seen_at`
- `last_seen_at`

### crawl_jobs

- `id`
- `job_type`
- `source`
- `query`
- `status`
- `started_at`
- `finished_at`
- `error_message`

### crawl_logs

- `id`
- `job_id`
- `url`
- `status_code`
- `fetched_at`
- `parser_status`
- `error_message`

### auth_sessions

- `id`
- `source`
- `storage_backend`
- `session_path`
- `created_at`
- `last_validated_at`
- `expires_hint`
- `status`
- `warning_acknowledged_at`

## 8. Crawl Flow

```text
User query
    |
Validate source policy and robots rules
    |
Load optional authenticated session (MVP 5 only; skipped in MVP 2)
    |
Build crawl job
    |
Fetch search/list page
    |
Parse comic results
    |
Upsert comics
    |
Fetch selected detail pages
    |
Parse chapter metadata
    |
Compare with stored chapters
    |
Generate update report
```

## 9. Authenticated Crawl Flow

This flow belongs to MVP 5. MVP 2 detail sync must remain anonymous/public-only.

```text
User runs auth login
    |
Open local browser
    |
User manually logs in on source website
    |
Save browser storage state locally
    |
Validate session with a lightweight account-visible page
    |
Run metadata or chapter sync with saved session
    |
Pause on expiration, CAPTCHA, 403, 429, or policy uncertainty
```

## 10. MVP Scope

### MVP 1: Metadata CLI

- Project skeleton. Status: completed in Unit 1.
- Config file. Status: baseline completed in Unit 1.
- SQLite database. Status: baseline completed in Unit 2.
- `search` command. Status: baseline completed in Unit 7; default prints results only, `--save` persists to SQLite.
- List/search page parsing. Status: baseline completed in Unit 4.
- Basic export. Status: baseline completed in Unit 3.

Unit 1 accepted scope:

- `pyproject.toml` with `src/` layout and `panelscout` CLI entry.
- `src/panelscout` package with CLI and config baseline.
- Placeholder subpackages for future modules.
- Safe `.gitignore` for Python caches, virtualenvs, local databases, cookies, session storage, and Playwright artifacts.
- Lightweight `unittest` coverage for CLI and config behavior.
- No crawling, login, network requests, parsing, storage writes, or downloads.

### MVP 2: Detail Sync

- Public/anonymous detail sync only.
- Detail page parsing. Status: baseline completed in Unit 8.
- Chapter metadata parsing. Status: baseline completed in Unit 8 and exposed through CLI in Unit 9.
- Comic and chapter upsert logic. Status: baseline completed in Unit 8.
- Update detection. Status: baseline `new_chapter_count` completed in Unit 8; richer chapter and metadata reports completed in Unit 10.
- `sync` command. Status: baseline completed in Unit 9; default dry-run, `--save` persists to SQLite.
- Authenticated Session Mode is explicitly out of MVP 2 and remains MVP 5.

### MVP 3: Watchlist

- Save comics to watchlist. Status: baseline completed in Unit 11.
- Scheduled update checks. Status: pending.
- Markdown update report. Status: pending.

### MVP 4: Local UI

- Search screen.
- Comic detail screen.
- Watchlist screen.
- Update history screen.

### MVP 5: Authenticated Session Mode

- `auth login` command using Playwright.
- Local session storage.
- Session status validation.
- Authenticated metadata sync.
- Automatic pause on expired or blocked sessions.
- Session file gitignore rules.

## 11. Suggested Technology Stack

- Language: Python 3.12+
- HTTP client: `httpx`
- HTML parser: `selectolax` or `beautifulsoup4`
- Browser automation: `playwright` for authenticated login and optional rendering fallback
- CLI framework: `typer`
- Database: SQLite
- ORM or query layer: SQLModel, SQLAlchemy Core, or plain SQL
- Scheduling: APScheduler
- Testing: pytest

## 12. Repository Layout

```text
panel-scout/
  README.md
  docs/
    design-document.md
  pyproject.toml
  src/
    panelscout/
      __init__.py
      cli.py
      config.py
      crawler/
        engine.py
        fetcher.py
        robots.py
        scheduler.py
      auth/
        session.py
        browser_login.py
        storage.py
      adapters/
        zaimanhua.py
      parsers/
        zaimanhua.py
      storage/
        database.py
        models.py
        repositories.py
      exporters/
        json_exporter.py
        csv_exporter.py
        markdown_exporter.py
  tests/
    fixtures/
    test_zaimanhua_parser.py
    test_auth_session.py
```

## 13. Safety and Compliance Requirements

- Check robots rules before crawling supported sources.
- Use conservative rate limits.
- Stop on repeated blocking responses.
- Keep a clear User-Agent.
- Do not collect or store plaintext credentials.
- Do not access pages outside the user's own account-visible scope.
- Do not access paid, removed, or restricted pages unless the user's account is explicitly authorized and the source policy allows it.
- Do not circumvent technical protections.
- Keep metadata and source attribution.
- Make download-related code opt-in and permission-gated.
- Store sessions only locally.
- Encrypt session storage or use an OS credential store when practical.
- Exclude session files, cookies, and local databases from git.

## 14. Feasibility Audit

Overall feasibility: medium-high for a local metadata and update tracker; medium for authenticated crawling; low for generalized content downloading without legal and technical risk.

### Feasible Now

- Metadata search, list parsing, and local cataloging are feasible with `httpx`, HTML parsing, and SQLite.
- Chapter update detection is feasible if detail pages expose stable chapter links or titles.
- CSV, JSON, and Markdown exports are straightforward.
- CLI-first delivery is feasible and keeps the first release small.
- Authenticated session reuse is feasible with Playwright storage state as long as the user logs in locally.

### Needs Early Validation

- ZaiManHua page structure may differ between public, mobile, original, and manhua subdomains.
- Some pages may require JavaScript rendering, so parser fixtures must be collected from both raw HTTP and Playwright-rendered HTML.
- Session lifetime and login verification behavior are unknown and should be tested before designing background sync.
- robots and source policy behavior should be checked per subdomain, not only at the top-level domain.
- Authenticated requests may behave differently from anonymous requests, especially around rate limits.

### Main Risks

- Copyright risk increases sharply if the project moves from metadata tracking to content archiving.
- Saved cookies are sensitive account material, even without storing passwords.
- Site layout changes can break parser selectors.
- Aggressive crawling can trigger blocking or account restrictions.
- A public hosted version would introduce privacy, abuse, and compliance problems and should remain out of scope.

### Recommended First Implementation Order

1. Build anonymous metadata search and parser tests.
2. Build SQLite storage and export.
3. Add detail sync and update detection.
4. Add Authenticated Session Mode with manual local login.
5. Add local UI after CLI behavior is stable.
6. Reassess downloader scope only after legal and source-policy review.

## 15. Implementation Progress

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

## 16. Open Questions

- Should the first interface be CLI-only or include a local web UI from day one?
- Which exact filters are required for the first search workflow?
- Should update reports be written to local Markdown files, desktop notifications, or both?
- Should the project support multiple comic sites after the first adapter is stable?
- Should authenticated session files use OS credential storage in MVP 5, or is encrypted local file storage acceptable for the first private release?
