# PanelScout

PanelScout is a local comic discovery and update-tracking tool. It is designed to collect public metadata, monitor chapter updates, and organize reading links from supported comic sites while respecting site rules, rate limits, and copyright boundaries.

Chinese name: 格探

## Current Stage

This repository has a tested local MVP baseline for public search, detail sync, explicit download planning/saving, local UI actions, and the first authenticated-session capture commands. Current architecture, scope, safety boundaries, and unit acceptance reports are recorded in [docs/design-document.md](docs/design-document.md) and [docs/unit-acceptance-reports.md](docs/unit-acceptance-reports.md).

## Guiding Principle

PanelScout defaults to metadata-only collection. Any content download feature must be explicitly enabled only for resources the user has permission to archive.
