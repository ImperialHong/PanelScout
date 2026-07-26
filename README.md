# PanelScout

PanelScout is a local comic discovery and update-tracking tool. It is designed to collect public metadata, monitor chapter updates, and organize reading links from supported comic sites while respecting site rules, rate limits, and copyright boundaries.

Chinese name: 格探

## Current Stage

This repository has a tested local MVP baseline for public search, detail sync, explicit download planning/saving, local UI actions, and the first authenticated-session capture commands. Current architecture, scope, safety boundaries, and unit acceptance reports are recorded in [docs/design-document.md](docs/design-document.md) and [docs/unit-acceptance-reports.md](docs/unit-acceptance-reports.md).

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
