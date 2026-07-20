# PanelScout Design Document

Version: 0.24

Date: 2026-07-20

Chinese name: 格探

## 1. Project Summary

PanelScout is a local comic discovery, cataloging, update-monitoring, and personal archiving application. The first supported source is ZaiManHua-related public pages and user-authorized account-visible pages. The software focuses on collecting metadata, tracking chapter changes, helping the user organize reading links, and saving user-authorized chapter images locally.

The project must not bypass login, paywalls, CAPTCHA, anti-hotlinking, encryption, access controls, or site-imposed restrictions. Login support must use a local user-driven browser session and must not collect or store plaintext passwords. Content download is a planned opt-in, permission-gated module for personal local use; it must never run silently by default.

## 2. Goals

- Search comics by keyword, author, category, status, theme, and audience.
- Store comic metadata locally.
- Store chapter list metadata and detect new chapters.
- Provide update notifications or update reports.
- Export collected metadata to CSV, JSON, or Markdown.
- Support a local authenticated session mode for content that the user's own account can normally view.
- Save user-authorized free or account-visible chapter images into a predictable local folder layout.
- Keep crawling polite, rate-limited, cache-aware, and observable.

## 2.1 Current Delivery Priority

Current highest priority: complete the minimum search-to-download business line before expanding secondary features or UI polish.

The minimum business line is:

```text
public search -> save comic -> public detail/chapter sync -> select chapter -> plan local download -> save chapter image files
```

Priority rules:

- Search, detail sync, chapter selection, download planning, and opt-in local save take precedence over additional watchlist, reporting, UI polish, scheduling, or multi-site features.
- Downloader work must remain personal-use, permission-gated, conservative, resumable, and source-policy aware.
- Public/anonymous content remains the current implementation path. Authenticated Session Mode stays in MVP 5 and must not block the anonymous minimum line.
- The project must first produce a working CLI-level minimum line. UI improvements should mirror the CLI line only after the core behavior is stable.
- If a source page or policy blocks image saving, the downloader must fail safely with a clear local error instead of attempting bypasses.

## 3. Non-Goals

- No collecting, transmitting, or storing plaintext usernames or passwords.
- No bypassing login, session expiration, CAPTCHA, or account checks.
- No accessing content unavailable to the user's own logged-in account.
- No CAPTCHA solving.
- No anti-bot evasion.
- No mass image mirroring or whole-site archiving by default.
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
- `download plan`: Preview local chapter image paths for an explicitly selected saved chapter.
- `download run`: Save explicitly selected public chapter images locally after user permission confirmation.
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

Downloader is an opt-in module for personal local archiving of chapters the user is authorized to view.

Current CLI baseline:

- Unit 18 added pure local file planning for `download_root/comic_title/chapter_title/001.ext`.
- Unit 19 added public chapter image discovery from saved/fetched chapter HTML.
- Unit 20 added `panelscout download plan` to preview file paths without fetching image bytes.
- Unit 21 added `panelscout download run` to explicitly save selected public chapter images.
- Unit 22 validated the minimum line from search/save through sync/chapter selection to local image save.

Rules:

- Disabled by default.
- Requires explicit user confirmation.
- Only works for content the user is authorized to archive.
- Must not bypass anti-hotlinking or restricted access.
- Must store source URL, crawl time, and permission note.
- Must use conservative concurrency and delay defaults.
- Must skip, resume, or verify already-downloaded files instead of redownloading blindly.
- Must write temporary files first and rename only after a complete image response is saved.
- Must preserve the original image extension when known.
- Must not include credentials, cookies, session state, or account identifiers in output folders.
- Current baseline does not use credentials, cookies, sessions, referer spoofing, browser automation, or background queues.

Output layout:

```text
download_root/
  Manga Title/
    Chapter Title/
      001.jpg
      002.png
    Chapter Title 2/
      001.jpg
```

Naming rules:

- The top-level manga directory is required so future chapter downloads for the same title share one local folder.
- Each chapter gets its own subdirectory under the manga directory.
- Directory format: `download_root/comic_title/chapter_title/`.
- Image file format: `page_number.ext`.
- Page numbers are zero-padded from `001`.
- `comic_title` and `chapter_title` must be filename-safe; replace `/ \ : * ? " < > |` and control characters.
- If two generated directories or file names collide, append a stable numeric suffix.
- Example: `伪恋同盟/第003话/001.jpg`.

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
- Scheduled update checks. Status: local suggested schedule baseline completed in Unit 14.
- Markdown update report. Status: completed in Unit 13.

### MVP 4: Local UI

MVP 4 was temporarily de-prioritized behind the minimum search-to-download business line. The CLI minimum line is now accepted through Unit 22, so the next MVP 4 work can resume by wiring the Chinese local UI to the accepted CLI download behavior.

- 搜索页。Status: static shell baseline completed in Unit 15; local SQLite data binding baseline completed in Unit 16; Chinese UI copy baseline completed in Unit 17.
- 本地库页。Status: static shell baseline completed in Unit 15; local SQLite data binding baseline completed in Unit 16; Chinese UI copy baseline completed in Unit 17.
- 漫画详情页。Status: static shell baseline completed in Unit 15; selected comic metadata and local chapter list binding completed in Unit 16; Chinese UI copy baseline completed in Unit 17.
- 追更页。Status: static shell baseline completed in Unit 15; local watchlist entries, notes, and checked-status binding completed in Unit 16; Chinese UI copy baseline completed in Unit 17.
- 更新历史页。Status: static shell baseline completed in Unit 15; local summary binding completed in Unit 16; Chinese UI copy baseline completed in Unit 17; persisted history stream pending.
- 章节选择与本地下载页。Status: static shell baseline completed in Unit 15; local chapter selector binding completed in Unit 16; Chinese UI copy baseline completed in Unit 17; CLI download plan/run baseline completed in Units 20-21; UI execution wiring pending.
- 下载队列/状态页。Status: static shell baseline completed in Unit 15; Chinese UI copy baseline completed in Unit 17; queue engine pending.
- 下载设置页。Status: static shell baseline completed in Unit 15; database path binding completed in Unit 16; Chinese UI copy baseline completed in Unit 17; settings persistence pending.

MVP 4 required UI elements:

- 默认 UI 语言：本地界面的用户可见文案使用简体中文。
- 顶部导航：搜索、本地库、追更、更新历史、下载、设置。
- 搜索工具栏：关键词输入、来源选择、搜索按钮、保存结果操作。
- 左侧结果/本地库区域：紧凑漫画卡片，包含标题、作者、状态、最新章节、来源漫画 ID 和快捷操作。
- 右侧详情区域：元数据摘要、详情地址、可见章节列表、同步操作、追更/取消追更操作、导出/报告操作。
- 章节选择器：复选框网格/列表、刷新章节操作、全选、清空选择和已选数量。
- 下载控制：下载选中章节、暂停/继续队列、重试失败项、打开下载目录。
- 下载队列标签：待处理、运行中、已完成、失败。
- 下载条目字段：漫画标题、章节标题、页数、已保存数量、当前图片、状态、速度、错误信息。
- 下载目录控制：根目录输入、打开目录按钮、命名预览 `comic_title/chapter_title/001.ext`。
- 追更面板：检查数量、新章节、元数据变化、失败项、最后检查时间、计划状态。
- 更新历史面板：最近追更检查摘要、Markdown 报告导出、失败项详情。
- 设置面板：数据库路径、下载根目录、来源、User-Agent、请求延迟、并发数、报告输出路径和日志。

MVP 4 UI boundaries:

- The UI may expose downloader controls, but download execution must remain explicit and user-triggered.
- Do not show login controls until MVP 5.
- Do not expose paid/VIP bypass, CAPTCHA solving, anti-bot evasion, or redistribution features.

MVP 4 current implementation note:

- Unit 15 ships a static local HTML shell via `panelscout ui build --output PATH`.
- Unit 16 reads the configured local SQLite database when it exists and renders saved catalog, chapter, watchlist, watch schedule, and local summary data into that static shell.
- Unit 17 makes the static local UI's user-visible copy Chinese by default, including navigation, headings, tables, buttons, empty states, disabled download text, core accessibility labels, and UI build output.
- Units 18-22 complete the CLI-level minimum search-to-download line, but the static UI still does not execute downloads directly.
- Missing and initialized-empty databases render explicit empty states; the UI build path does not create the default user-home database just to render the shell.
- The current UI shell is a local artifact only; it does not start a server, live network request, auth flow, browser automation, downloader engine, image fetcher, background daemon, or scheduler.
- Download action buttons are visible for planning but disabled, and the folder preview follows `download_root/漫画名/章节名/001.jpg`.

### MVP 5: Authenticated Session Mode

MVP 5 remains deferred until the anonymous/public minimum search-to-download line is complete.

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
      downloader/
        discovery.py
        fetcher.py
        planner.py
        workflow.py
        queue.py
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
- Download only chapters the user is authorized to view; never attempt paid/VIP/restricted bypass.
- Downloaded files are for personal local use and must not add redistribution, sharing, or publishing workflows.
- Keep downloader defaults polite: low concurrency, request delays, retries with backoff, and clear failure states.
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

- Copyright risk increases sharply when the project moves from metadata tracking to content archiving; downloader scope must stay personal, explicit, and source-policy aware.
- Saved cookies are sensitive account material, even without storing passwords.
- Site layout changes can break parser selectors.
- Aggressive crawling can trigger blocking or account restrictions.
- A public hosted version would introduce privacy, abuse, and compliance problems and should remain out of scope.

### Recommended First Implementation Order

1. Finish the already-started anonymous metadata line: search, save, detail sync, chapter metadata, and CLI persistence. Status: completed.
2. Build downloader planner and filename/layout rules for `download_root/comic_title/chapter_title/001.ext`. Status: completed in Unit 18.
3. Add chapter image discovery from public chapter pages using local fixtures first, with no bypass behavior. Status: completed in Unit 19.
4. Add opt-in CLI download execution for explicitly selected local chapters, with permission notes, conservative delays, temporary files, resume/skip behavior, and failure logging. Status: completed in Units 20-21.
5. Validate the full minimum line end to end: search -> save -> sync chapters -> select chapter -> download to local folders. Status: completed in Unit 22.
6. Resume MVP 4 by wiring the Chinese UI to the accepted CLI/download status.
7. Keep Authenticated Session Mode in MVP 5 until the anonymous/public UI-facing download line is stable and safe.
8. Reassess downloader scope continuously against legal and source-policy risk.

## 15. Implementation Progress

Detailed Unit-level implementation and validation reports are maintained separately: [Unit Acceptance Reports](unit-acceptance-reports.md).

Current accepted range: Unit 1 through Unit 22.

Latest accepted Unit: Unit 22, End-to-End Minimum Line Validation.

High-level milestone status:

- MVP 1: Project skeleton, SQLite storage, exporters, anonymous parser fixtures, robots policy, fetcher baseline, public search workflow, and safe CLI search integration are accepted.
- MVP 2: Public detail sync, chapter metadata upsert, safe CLI sync integration, richer sync result, and report output are accepted. Authenticated Session Mode remains deferred to MVP 5.
- MVP 3: Local watchlist, public watch update checks, Markdown watch reports, and local suggested watch schedule baseline are accepted.
- Minimum search-to-download line: Search, save, public detail/chapter sync, chapter selection, download plan, and explicit local image save are accepted at CLI/workflow level.
- MVP 4: Static local UI shell, local SQLite data binding, and Chinese UI copy baseline are accepted. Next work should expose the accepted minimum line through the local UI without adding auth or background queues.
- MVP 5: Authenticated Session Mode is not started.

## 16. Next Unit Plan

Current priority: resume MVP 4 UI wiring on top of the accepted minimum search-to-download business line.

Planned next Units:

- Unit 23: UI download command bridge. Render selected chapter, output root, permission note, and copyable CLI command previews in Chinese without executing downloads from the static page.
- Unit 24: UI download status import. Read locally generated download folders and show saved/missing/failed counts for selected chapters.
- Unit 25: UI-to-local-runner decision. Decide whether MVP 4 stays static-command-driven or adds a local-only service runner; any runner must remain explicit, local, and disabled until launched by the user.
- Unit 26+: UX polish for search/detail/download flow after the UI has a safe path to the accepted CLI behavior.

## 17. Open Questions

- Should the first interface be CLI-only or include a local web UI from day one?
- Which exact filters are required for the first search workflow?
- Should update reports be written to local Markdown files, desktop notifications, or both?
- Should the project support multiple comic sites after the first adapter is stable?
- Should authenticated session files use OS credential storage in MVP 5, or is encrypted local file storage acceptable for the first private release?
