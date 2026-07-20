# PanelScout Design Document

Version: 0.1

Date: 2026-07-20

Chinese name: 格探

## 1. Project Summary

PanelScout is a local comic discovery, cataloging, and update-monitoring application. The first supported source is ZaiManHua-related public pages. The software focuses on collecting public metadata, tracking chapter changes, and helping the user organize reading links.

The project must not bypass login, paywalls, CAPTCHA, anti-hotlinking, encryption, access controls, or site-imposed restrictions. Content download is not part of the default MVP and must remain an opt-in, permission-gated module.

## 2. Goals

- Search comics by keyword, author, category, status, theme, and audience.
- Store comic metadata locally.
- Store chapter list metadata and detect new chapters.
- Provide update notifications or update reports.
- Export collected metadata to CSV, JSON, or Markdown.
- Keep crawling polite, rate-limited, cache-aware, and observable.

## 3. Non-Goals

- No bypassing login-only or restricted content.
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

## 8. Crawl Flow

```text
User query
    |
Validate source policy and robots rules
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

## 9. MVP Scope

### MVP 1: Metadata CLI

- Project skeleton.
- Config file.
- SQLite database.
- `search` command.
- List/search page parsing.
- Basic export.

### MVP 2: Detail Sync

- Detail page parsing.
- Chapter metadata parsing.
- Comic and chapter upsert logic.
- Update detection.

### MVP 3: Watchlist

- Save comics to watchlist.
- Scheduled update checks.
- Markdown update report.

### MVP 4: Local UI

- Search screen.
- Comic detail screen.
- Watchlist screen.
- Update history screen.

## 10. Suggested Technology Stack

- Language: Python 3.12+
- HTTP client: `httpx`
- HTML parser: `selectolax` or `beautifulsoup4`
- Optional browser fallback: `playwright`
- CLI framework: `typer`
- Database: SQLite
- ORM or query layer: SQLModel, SQLAlchemy Core, or plain SQL
- Scheduling: APScheduler
- Testing: pytest

## 11. Repository Layout

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
```

## 12. Safety and Compliance Requirements

- Check robots rules before crawling supported sources.
- Use conservative rate limits.
- Stop on repeated blocking responses.
- Keep a clear User-Agent.
- Do not access private, paid, or restricted pages.
- Do not circumvent technical protections.
- Keep metadata and source attribution.
- Make download-related code opt-in and permission-gated.

## 13. Open Questions

- Should the first interface be CLI-only or include a local web UI from day one?
- Which exact filters are required for the first search workflow?
- Should update reports be written to local Markdown files, desktop notifications, or both?
- Should the project support multiple comic sites after the first adapter is stable?
