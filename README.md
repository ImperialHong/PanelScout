# PanelScout

PanelScout is a local comic discovery and update-tracking tool. It is designed to collect public metadata, monitor chapter updates, and organize reading links from supported comic sites while respecting site rules, rate limits, and copyright boundaries.

Chinese name: 格探

## Current Stage

This repository has a tested local MVP baseline for public and authenticated search, detail sync, explicit download planning/saving, local UI actions, and authenticated-session capture/reuse. Current architecture, scope, safety boundaries, and unit acceptance reports are recorded in [docs/design-document.md](docs/design-document.md) and [docs/unit-acceptance-reports.md](docs/unit-acceptance-reports.md).

## Windows Portable Release

PanelScout now has a Windows release baseline for non-developer users. The release workflow builds a portable `PanelScout-*-windows-x64.zip` on GitHub Actions, bundles Playwright Chromium for authenticated login/rendering, and publishes the zip as a workflow artifact or tagged GitHub Release asset.

Windows users can extract the zip and double-click `PanelScout.exe`; the app starts a local-only UI at `http://127.0.0.1:8765/` and opens the default browser. Usage notes are in [packaging/windows/README-Windows.md](packaging/windows/README-Windows.md).

## Guiding Principle

PanelScout defaults to metadata-only collection. Any content download feature must be explicitly enabled only for resources the user has permission to archive.

## Live Auth Smoke Tests

Live authenticated smoke tests are disabled by default. To run them locally, copy `.env.example` to `.env.local`, fill in a dedicated test account, set `PANELSCOUT_LIVE_AUTH=1`, and keep `.env.local` out of git:

```bash
cp .env.example .env.local
```

Then run:

```bash
PYTHONPATH=src .venv/bin/python -m unittest tests.test_live_auth_smoke
```

This test logs in with environment-provided credentials only for the current local test run, then saves temporary browser storage state under the test temp directory. Do not commit real usernames, passwords, cookies, or storage-state files.

Authenticated live workflows can reuse the saved local browser session for JavaScript-rendered search, detail sync, and chapter-page rendering:

```bash
PYTHONPATH=src .venv/bin/panelscout search "伪恋同盟" --auth --save
PYTHONPATH=src .venv/bin/panelscout sync 15599 --auth --save
PYTHONPATH=src .venv/bin/panelscout download run 15599 --chapter "第01话" --auth --permission-note "用户确认该账号可访问该章节，仅用于本机开发烟测。"
```

Authenticated chapter rendering switches supported reader pages to `滚动阅读` and records the rendered DOM/network image URLs before planning file paths.

The interactive local UI can create and reuse the same saved session. Start it locally, click the right-side `登录` button, and enter the source account for the current local run. After login, the button shows the account ID and exposes `退出登录`; authenticated search, detail sync, and download execution then reuse the saved local browser storage state. Passwords are not stored. The download panel supports multi-select/all-select chapter picking, includes a folder button for choosing the target directory, and lets the user add selected chapters to a local in-memory background queue for sequential download. The confirmation note is handled through the local download action rather than shown as an editable field.

```bash
PYTHONPATH=src .venv/bin/panelscout ui serve
```

If the UI reports that the auth session is not configured or the session file is missing, click `登录` again or run `panelscout auth login zaimanhua --acknowledge-local-session-storage` and retry.
