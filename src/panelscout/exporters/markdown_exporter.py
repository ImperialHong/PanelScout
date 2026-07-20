"""Markdown exporter for stored comic metadata."""

from __future__ import annotations

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


def _append_optional(lines: list[str], label: str, value: str | None) -> None:
    if value:
        lines.append(f"- {label}: {value}")


def _escape_heading(value: str) -> str:
    return value.replace("\n", " ").strip()
