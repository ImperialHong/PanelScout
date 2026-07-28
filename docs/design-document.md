# PanelScout Design Document

Version: 0.38

Date: 2026-07-28

Chinese name: 格探

## 1. Project Summary

PanelScout is a local comic discovery, cataloging, update-monitoring, and personal archiving application. The first supported source is ZaiManHua-related public pages and user-authorized account-visible pages. The software focuses on collecting metadata, tracking chapter changes, helping the user organize reading links, and saving user-authorized chapter images locally.

The project must not bypass login, paywalls, CAPTCHA, anti-hotlinking, encryption, access controls, or site-imposed restrictions. Login support normally uses a local user-driven browser session. Development-only live smoke tests may read a dedicated test username and password from git-ignored local environment variables, but the project must not commit, log, or persist plaintext passwords. Content download is a planned opt-in, permission-gated module for personal local use; it must never run silently by default.

## 2. Goals

- Search comics by keyword, author, category, status, theme, and audience.
- Store comic metadata locally.
- Store chapter list metadata and detect new chapters.
- Provide update notifications or update reports.
- Export collected metadata to CSV, JSON, or Markdown.
- Support a local authenticated session mode for content that the user's own account can normally view.
- Save user-authorized free or account-visible chapter images into a predictable local folder layout.
- Keep crawling polite, rate-limited, cache-aware, and observable.
- Provide a Windows portable release package that starts the local-only UI for non-developer users.

## 2.1 Current Delivery Priority

Current highest priority: expose the accepted minimum search-to-download business line through the Chinese local UI before expanding secondary features or deeper UI polish.

The minimum business line is:

```text
search -> save comic -> detail/chapter sync -> select chapter -> plan local download -> save chapter image files
```

Priority rules:

- Search, detail sync, chapter selection, download planning, opt-in local save, and UI command/status wiring take precedence over additional watchlist, reporting, scheduling, or multi-site features.
- Downloader work must remain personal-use, permission-gated, conservative, resumable, and source-policy aware.
- Public/anonymous content remains available. Authenticated Session Mode is now an explicit CLI/local UI option that reuses saved local browser storage state and must not weaken the anonymous minimum line.
- The project must first produce a working CLI-level minimum line. UI improvements should mirror the CLI line only after the core behavior is stable.
- If a source page or policy blocks image saving, the downloader must fail safely with a clear local error instead of attempting bypasses.

## 3. Non-Goals

- No committing, logging, or persisting plaintext usernames or passwords. Development-only smoke tests may read a dedicated test account from git-ignored local environment variables for a single run.
- No bypassing login, session expiration, CAPTCHA, or account checks.
- No accessing content unavailable to the user's own logged-in account.
- No CAPTCHA solving.
- No anti-bot evasion.
- No mass image mirroring or whole-site archiving by default.
- No redistribution or sharing workflow for copyrighted content.
- No public hosted scraping service in the first version.
- No bundled plaintext credentials or account-specific release artifacts.

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
- Unit 23 added Chinese UI command previews and changed the default configured download root to `/downloads`.
- Unit 24 changed the default configured download root to the macOS default Downloads folder, `~/Downloads`.
- Unit 25 adds local download status reading from `download_root/comic_title/chapter_title`.
- Unit 26 adds `panelscout ui serve`, a foreground local runner bound to `127.0.0.1`.
- Unit 27 wires the interactive Chinese UI to public search/save and detail/chapter sync APIs.
- Unit 28 wires the UI to explicit download plan/run APIs.
- Unit 29 returns local saved/partial download status for selected chapters.
- Unit 38 adds a local in-memory background queue for the interactive UI. `/api/download/enqueue` accepts one or more selected chapters, `/api/download/queue` returns the current queue snapshot, and a single worker thread saves queued chapters sequentially.

Default download root:

- `download_root` defaults to `~/Downloads`, expanded at runtime to the current macOS user's Downloads folder, for example `/Users/jay/Downloads`.
- Users may override it in config with `[paths] download_root = "/some/path"`.
- CLI `download plan` and `download run` use the configured `download_root` when `--output-root` is omitted.
- On systems where the configured download root is not writable, execution fails cleanly and the user must provide or create a writable path outside PanelScout.

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
- Background queue execution must be local-only, user-triggered, sequential by default, and must not persist credentials or plaintext passwords in queued job payloads.
- CLI public downloader execution does not use credentials, cookies, sessions, referer spoofing, browser automation, or background queues. Authenticated UI/CLI paths may reuse the user's saved local browser session, and the interactive UI now has an explicit local-only background queue.

Output layout:

```text
~/Downloads/
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
- Default directory format: `~/Downloads/comic_title/chapter_title/`.
- If `download_root` is overridden, directory format becomes `download_root/comic_title/chapter_title/`.
- Image file format: `page_number.ext`.
- Page numbers are zero-padded from `001`.
- `comic_title` and `chapter_title` must be filename-safe; replace `/ \ : * ? " < > |` and control characters.
- If two generated directories or file names collide, append a stable numeric suffix.
- Example: `伪恋同盟/第003话/001.jpg`.

### 6.10 Authenticated Session Mode

Authenticated Session Mode allows PanelScout to access pages that are visible only after the user logs in with their own free account.

This mode defaults to local browser-based login. Development live smoke tests may automate login with a dedicated test account read from git-ignored environment variables, then immediately convert that login into local browser storage state for the rest of the workflow.

Recommended command flow:

- `panelscout auth login zaimanhua --acknowledge-local-session-storage`: Open a local Playwright browser window and let the user log in manually.
- `panelscout auth status zaimanhua`: Check whether a saved session still appears valid.
- `panelscout auth logout zaimanhua`: Delete the saved local session.
- `panelscout search "伪恋同盟" --auth [zaimanhua] --save`: Reuse the saved session for JavaScript-rendered search.
- `panelscout sync 15599 --auth [zaimanhua] --save`: Reuse the saved session for metadata and chapter sync.
- `panelscout download plan/run 15599 --chapter "第01话" --auth [zaimanhua]`: Reuse the saved session while rendering selected chapter pages.
- `panelscout ui serve`: Start the local UI; the right-side `登录` button captures a local browser storage-state session, then the account menu exposes `退出登录`.

Current baseline:

- Unit 30 starts Authenticated Session Mode with `panelscout auth login/status/logout`.
- `auth login` requires explicit acknowledgement that local storage-state files contain sensitive cookies/session data.
- CLI `auth login` uses optional Playwright browser capture when the auth extra is installed; it never asks for usernames or passwords.
- `auth status` currently reads local metadata and whether the storage-state file exists. Server-side validation is not wired yet.
- `auth logout` deletes the recorded local storage-state file and SQLite session metadata.
- Unit 31 wires `sync --auth` to the saved storage-state file through an optional Playwright authenticated HTML fetcher.
- Unit 32 adds a default-skipped live authenticated smoke test harness that reads credentials only from `.env.local` or process environment when `PANELSCOUT_LIVE_AUTH=1`.
- Unit 33 wires `search --auth` and `download plan/run --auth` to the saved storage-state file for JavaScript-rendered search and chapter-page rendering.
- Unit 34 wires the interactive local UI search, sync, download plan, and download run requests to the same authenticated fetcher path when a saved session is enabled.
- Unit 35 switches supported authenticated reader pages to `滚动阅读` and snapshots rendered DOM/network image URLs before chapter image discovery.
- Unit 36 simplifies the initial UI, replaces the visible auth switch with a `登录`/account menu, removes low-value plan/status buttons from the interactive download panel, adds multi-select/all-select chapters and a local download-directory picker, keeps the queue updated during download execution, and lets the local UI capture/logout the saved session without storing plaintext passwords.
- Unit 38 changes the interactive UI download action from synchronous run-and-wait to enqueue-and-poll. Users can add selected chapters to the background queue while earlier downloads are still running.
- Authenticated download page rendering filters out reader chrome, logos, and layout images before planning files, then keeps image byte fetching on the existing conservative fetcher.
- Server-side session validation remains response-driven only: blocked, expired, CAPTCHA, or restricted sessions must fail clearly instead of attempting recovery or bypass.
- Public search/download workflows remain available when auth is disabled.

Rules:

- CLI manual login has the user enter credentials directly into the website in a local browser window.
- Local UI credential login accepts credentials only for the active local request, submits them to the configured source through Playwright, and saves only browser storage state.
- The development live smoke test may receive a dedicated test account through git-ignored local environment variables.
- PanelScout never commits, logs, stores, or uploads plaintext credentials.
- CAPTCHA or additional verification must fail clearly or be handled by falling back to manual browser login.
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

### 6.11 Release Packaging

Release packaging is local-app distribution only. The first supported release target is a Windows x64 portable zip.

Current baseline:

- Unit 37 adds `panelscout.windows_launcher`, a double-click-friendly launcher that starts `serve_local_ui` on `127.0.0.1`, opens the default browser, and keeps the console window visible while the app runs.
- Unit 37 adds a PyInstaller spec under `packaging/windows/` and a GitHub Actions workflow for `windows-latest`.
- The workflow installs the optional packaging dependencies, sets `PLAYWRIGHT_BROWSERS_PATH=0`, installs Chromium with Playwright, runs Windows release checks, builds `PanelScout.exe`, copies Windows instructions into `dist/PanelScout`, zips the folder, uploads the artifact, and publishes it to GitHub Releases when the build is triggered by a `v*` tag.

Rules:

- Release artifacts must not include `.env.local`, credentials, cookies, storage-state files, local databases, or downloaded comics.
- The packaged app must remain local-only and bind to `127.0.0.1`.
- The first release can be unsigned; Windows SmartScreen warnings must be documented.
- Passwords are accepted only through the active local login flow and must not be persisted.

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
Unit 30 implements the login capture/status/logout baseline. Unit 31 adds authenticated detail sync reuse for saved browser storage state.

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

MVP 4 was temporarily de-prioritized behind the minimum search-to-download business line. The CLI minimum line is accepted through Unit 22. Units 23-24 add static UI download command previews and the macOS Downloads default. Units 25-29 add a local-only runner/API and connect the Chinese UI to the accepted search, sync, download plan/run, and download-status workflows.

- 搜索页。Status: static shell baseline completed in Unit 15; local SQLite data binding baseline completed in Unit 16; Chinese UI copy baseline completed in Unit 17.
- 本地库页。Status: static shell baseline completed in Unit 15; local SQLite data binding baseline completed in Unit 16; Chinese UI copy baseline completed in Unit 17.
- 漫画详情页。Status: static shell baseline completed in Unit 15; selected comic metadata and local chapter list binding completed in Unit 16; Chinese UI copy baseline completed in Unit 17.
- 追更页。Status: static shell baseline completed in Unit 15; local watchlist entries, notes, and checked-status binding completed in Unit 16; Chinese UI copy baseline completed in Unit 17.
- 更新历史页。Status: static shell baseline completed in Unit 15; local summary binding completed in Unit 16; Chinese UI copy baseline completed in Unit 17; persisted history stream pending.
- 章节选择与本地下载页。Status: static shell baseline completed in Unit 15; local chapter selector binding completed in Unit 16; Chinese UI copy baseline completed in Unit 17; CLI download plan/run baseline completed in Units 20-21; UI command bridge completed in Unit 23; local runner/API download plan/run wiring completed in Unit 28.
- 下载队列/状态页。Status: static shell baseline completed in Unit 15; Chinese UI copy baseline completed in Unit 17; local saved/partial status read completed in Unit 29; local in-memory background queue completed in Unit 38; persistent queue recovery remains pending.
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
- Unit 23 renders copyable `panelscout download plan/run` command previews for the selected local chapter.
- Unit 24 renders the macOS default Downloads folder as the default download root.
- Unit 25 adds reusable local download status reading without fetching chapter HTML or images.
- Unit 26 adds `panelscout ui serve`, a foreground local HTTP runner/API that only binds to `127.0.0.1`.
- Unit 27 adds interactive UI calls for public search/save and public detail/chapter sync.
- Unit 28 adds interactive UI calls for explicit download plan/run using the accepted downloader workflow and permission note.
- Unit 29 adds interactive UI status reads for saved and partial files in the selected chapter directory.
- Unit 34 routes interactive local UI search/sync/download page rendering through the saved authenticated browser session when enabled.
- Unit 36 replaces the visible auth switch with a `登录`/account menu, adds multi-select/all-select chapter controls and a target-directory picker, removes the visible permission-note field and low-value plan/status buttons, and keeps download history/status in the primary workspace.
- Unit 38 adds a local in-memory download queue owned by the running `PanelScoutUiApi` instance. The UI submits selected chapters to `/api/download/enqueue`, polls `/api/download/queue`, and leaves the user free to add more chapters while one worker thread processes jobs sequentially.
- Missing and initialized-empty databases render explicit empty states; the UI build path does not create the default user-home database just to render the shell.
- The static `ui build` shell remains a local artifact only; it does not start a server, live network request, auth flow, browser automation, downloader engine, image fetcher, background daemon, or scheduler.
- The interactive `ui serve` shell calls only the local PanelScout runner. It can trigger public or explicitly authenticated search/sync/download workflows only after user actions, and it does not call third-party websites directly from browser JavaScript.
- Download action buttons in the interactive runner are user-triggered and send an explicit local UI confirmation marker. Queue jobs live only for the current local server process and are not restored after restart.

### MVP 5: Authenticated Session Mode

MVP 5 has started after the anonymous/public minimum search-to-download line reached the local UI.

- `auth login` command using optional Playwright. Status: baseline completed in Unit 30.
- Local session storage. Status: baseline completed in Unit 30.
- Session status readout. Status: local metadata/file status completed in Unit 30; server validation pending.
- Authenticated metadata sync. Status: detail sync reuse baseline completed in Unit 31.
- Authenticated search and chapter-page rendering. Status: CLI baseline completed in Unit 33.
- Authenticated local UI reuse. Status: interactive UI/API baseline completed in Unit 34.
- Authenticated lazy-loaded reader discovery. Status: scroll-reader baseline completed in Unit 35.
- Automatic pause on expired or blocked sessions.
- Session file gitignore rules. Status: baseline completed before Unit 30.

## 11. Suggested Technology Stack

- Language: Python 3.12+
- HTTP client: `httpx`
- HTML parser: `selectolax` or `beautifulsoup4`
- Browser automation: `playwright` for authenticated login and optional rendering fallback
- Windows packaging: PyInstaller with bundled Playwright Chromium
- Release automation: GitHub Actions
- CLI framework: `typer`
- Database: SQLite
- ORM or query layer: SQLModel, SQLAlchemy Core, or plain SQL
- Scheduling: APScheduler
- Testing: pytest

## 12. Repository Layout

```text
panel-scout/
  README.md
  .github/
    workflows/
      windows-release.yml
  docs/
    design-document.md
  packaging/
    windows/
      README-Windows.md
      panelscout_windows.spec
  pyproject.toml
  src/
    panelscout/
      __init__.py
      cli.py
      config.py
      windows_launcher.py
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
6. Resume MVP 4 by wiring the Chinese UI to the accepted search/sync/download/status workflows. Status: completed through Unit 29 at fixture-test level.
7. Harden the local UI business flow with clearer empty states, progress display, and manual smoke checks before adding secondary UI features. Status: in progress after Unit 34.
8. Continue Authenticated Session Mode in MVP 5 with server-side session validation and clearer expired-session recovery.
9. Reassess downloader scope continuously against legal and source-policy risk.

## 15. Implementation Progress

Detailed Unit-level implementation and validation reports are maintained separately: [Unit Acceptance Reports](unit-acceptance-reports.md).

Current accepted range: Unit 1 through Unit 38.

Latest accepted Unit: Unit 38, Local UI Background Download Queue.

High-level milestone status:

- MVP 1: Project skeleton, SQLite storage, exporters, anonymous parser fixtures, robots policy, fetcher baseline, public search workflow, and safe CLI search integration are accepted.
- MVP 2: Public detail sync, chapter metadata upsert, safe CLI sync integration, richer sync result, and report output are accepted. Authenticated Session Mode remains deferred to MVP 5.
- MVP 3: Local watchlist, public watch update checks, Markdown watch reports, and local suggested watch schedule baseline are accepted.
- Minimum search-to-download line: Search, save, detail/chapter sync, chapter selection, download plan, and explicit local image save are accepted at CLI/workflow level for public mode and at live-smoke level for authenticated mode, including lazy-loaded scroll-reader chapters.
- MVP 4: Static local UI shell, local SQLite data binding, Chinese UI copy baseline, UI command bridge, local-only UI runner/API, UI search/save, UI detail/chapter sync, UI download plan/run, UI download status read, and in-memory background download queue are accepted at fixture-test level.
- MVP 5: Authenticated Session Mode has accepted login capture/status/logout, authenticated sync, authenticated search, authenticated chapter-page rendering, authenticated local UI reuse, and scroll-reader lazy image discovery baselines. Server-side validation and recovery UX remain pending.
- Distribution: Windows portable zip packaging is accepted at repository/workflow level; a real GitHub Actions run on `windows-latest` is the next release gate.

## 16. Next Unit Plan

Current priority: smoke-test the local UI background queue with real authenticated search, chapter multi-select/all-select, folder picking, queue append while running, and completed file verification.

Planned next Units:

- Unit 23: UI download command bridge. Status: accepted; no direct UI execution.
- Unit 24: macOS Downloads default and smoke test. Status: accepted.
- Unit 25: UI download status import. Status: accepted; reads local generated download folders and reports saved/partial files.
- Unit 26: Local UI runner/API. Status: accepted; `panelscout ui serve` binds to `127.0.0.1`.
- Unit 27: UI search/save and detail/chapter sync. Status: accepted through local API endpoints.
- Unit 28: UI download plan/run. Status: accepted through explicit local API endpoints.
- Unit 29: UI download status readout. Status: accepted through local API endpoint and downloader status module.
- Unit 30: Auth session login/status/logout baseline. Status: accepted.
- Unit 31: Authenticated detail sync reuse. Status: accepted.
- Unit 32: Live auth smoke env harness. Status: accepted.
- Unit 33: Authenticated search-to-download live smoke. Status: accepted.
- Unit 34: Authenticated local UI/API reuse. Status: accepted.
- Unit 35: Authenticated scroll-reader image discovery. Status: accepted.
- Unit 36: UI business-flow hardening: simplified search-first shell, login/account menu, chapter multi-select/all-select, directory picker, resilient download queue updates, clearer selected-chapter state, progress/readout polish, expired-session recovery copy, and manual local runner smoke checks. Status: accepted.
- Unit 37: Windows portable release baseline: launcher, PyInstaller spec, Windows instructions, and GitHub Actions artifact/release workflow. Status: accepted at repository/workflow level; Windows runner artifact smoke remains the release gate.
- Unit 38: Local UI background download queue: enqueue selected chapters, poll queue status, keep one sequential worker active, and allow new tasks to be added while earlier jobs run. Status: accepted at fixture-test level.

## 17. Open Questions

- Should the first interface be CLI-only or include a local web UI from day one?
- Which exact filters are required for the first search workflow?
- Should update reports be written to local Markdown files, desktop notifications, or both?
- Should the project support multiple comic sites after the first adapter is stable?
- Should authenticated session files use OS credential storage in MVP 5, or is encrypted local file storage acceptable for the first private release?
