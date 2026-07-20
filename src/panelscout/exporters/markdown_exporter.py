"""Markdown exporters for stored comic metadata and watch checks."""

from __future__ import annotations

from typing import Any
from typing import Iterable

from panelscout.storage.models import Comic


def export_comics_markdown(comics: Iterable[Comic]) -> str:
    """Return stored comic metadata as a readable Markdown watchlist."""

    comic_list = list(comics)
    lines = ["# PanelScout Comic Metadata", ""]

    if not comic_list:
        lines.append("_No stored comics._")
        return "\n".join(lines) + "\n"

    for comic in comic_list:
        lines.append(f"## {_escape_heading(comic.title)}")
        lines.append("")
        lines.append(f"- Source: `{comic.source}`")
        lines.append(f"- Source comic ID: `{comic.source_comic_id}`")
        _append_optional(lines, "Author", comic.author)
        _append_optional(lines, "Status", comic.status)
        _append_optional(lines, "Audience", comic.audience)
        if comic.categories:
            lines.append(f"- Categories: {', '.join(comic.categories)}")
        if comic.tags:
            lines.append(f"- Tags: {', '.join(comic.tags)}")
        _append_optional(lines, "Latest chapter", comic.latest_chapter_title)
        _append_optional(lines, "Detail URL", comic.detail_url)
        _append_optional(lines, "Cover URL", comic.cover_url)
        _append_optional(lines, "First seen", comic.first_seen_at)
        _append_optional(lines, "Last checked", comic.last_checked_at)
        _append_optional(lines, "Updated", comic.updated_at)
        if comic.summary:
            lines.extend(["", comic.summary])
        lines.append("")

    return "\n".join(lines)


def export_watch_check_markdown(result: Any) -> str:
    """Return a readable Markdown report for one public watchlist check."""

    lines = [
        "# PanelScout Watch Check Report",
        "",
        "## Summary",
        "",
        f"- Checked: {result.checked_count}",
        f"- Succeeded: {result.success_count}",
        f"- Failed: {result.failure_count}",
        f"- New chapters: {result.new_chapter_count}",
        f"- Metadata changes: {result.metadata_change_count}",
        "",
    ]

    if not result.items:
        lines.append("_No watched comics to check._")
        return "\n".join(lines) + "\n"

    lines.append("## Results")
    lines.append("")

    for item in result.items:
        comic = item.entry.comic
        lines.append(f"### {_escape_heading(comic.title)}")
        lines.append("")
        lines.append(f"- Source: `{comic.source}`")
        lines.append(f"- Source comic ID: `{comic.source_comic_id}`")
        _append_optional(lines, "Latest chapter", comic.latest_chapter_title)
        _append_optional(lines, "Detail URL", comic.detail_url)
        _append_optional(lines, "Watchlist last checked", item.entry.last_checked_at)

        if item.error:
            lines.append("- Status: failed")
            lines.append(f"- Error: {item.error}")
            lines.append("")
            continue

        sync_result = item.sync_result
        if sync_result is None:
            lines.append("- Status: skipped")
            lines.append("")
            continue

        lines.append("- Status: checked")
        lines.append(f"- New chapters: {sync_result.new_chapter_count}")
        lines.append(f"- Metadata changes: {len(sync_result.metadata_changes)}")

        if sync_result.new_chapters:
            lines.append("")
            lines.append("New chapter details:")
            for chapter in sync_result.new_chapters:
                lines.append(f"- [{chapter.title}]({chapter.chapter_url})")

        if sync_result.metadata_changes:
            lines.append("")
            lines.append("Metadata changes:")
            for change in sync_result.metadata_changes:
                lines.append(
                    f"- {_display_metadata_field(change.field)}: "
                    f"{_display_optional(change.previous)} -> "
                    f"{_display_optional(change.current)}"
                )

        lines.append("")

    return "\n".join(lines)


def _append_optional(lines: list[str], label: str, value: str | None) -> None:
    if value:
        lines.append(f"- {label}: {value}")


def _escape_heading(value: str) -> str:
    return value.replace("\n", " ").strip()


def _display_metadata_field(field: str) -> str:
    labels = {
        "title": "Title",
        "author": "Author",
        "status": "Status",
        "latest_chapter_title": "Latest chapter",
    }
    return labels.get(field, field)


def _display_optional(value: str | None) -> str:
    return value if value else "(none)"
