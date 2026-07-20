"""Static MVP4 local UI shell renderer."""

from __future__ import annotations

from html import escape
from pathlib import Path

from panelscout.ui.state import LocalUiState, UiComic, sample_local_ui_state


NAV_ITEMS = (
    "Search",
    "Local Library",
    "Watchlist",
    "Update History",
    "Downloads",
    "Settings",
)

DOWNLOAD_LAYOUT_PREVIEW = "download_root/漫画名/001话/001.jpg"


def build_local_ui_shell(state: LocalUiState | None = None) -> str:
    """Render the static MVP4 local UI shell.

    The artifact is a plain local HTML file. Controls that imply downloading
    remain visible for planning but disabled.
    """

    use_fallback_preview = state is None
    ui_state = state or sample_local_ui_state()
    nav = "\n".join(
        f'        <a class="nav-item" href="#{_anchor(item)}">{item}</a>'
        for item in NAV_ITEMS
    )
    search_value = ui_state.selected_comic.title if ui_state.selected_comic else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PanelScout Local UI</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --line: #d7dde6;
      --muted: #5d6978;
      --text: #17202a;
      --accent: #f06a00;
      --accent-soft: #fff0e4;
      --ok: #127a45;
      --warn: #9a5a00;
      --bad: #aa2d2d;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      display: flex;
      align-items: center;
      gap: 16px;
      height: 48px;
      padding: 0 16px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }}
    .brand {{
      font-weight: 700;
      min-width: 132px;
    }}
    nav {{
      display: flex;
      align-items: center;
      gap: 4px;
      overflow-x: auto;
      white-space: nowrap;
    }}
    .nav-item {{
      color: var(--text);
      text-decoration: none;
      padding: 12px 10px 10px;
      border-bottom: 2px solid transparent;
    }}
    .nav-item:first-child {{
      color: var(--accent);
      border-color: var(--accent);
    }}
    main {{
      display: grid;
      grid-template-columns: minmax(310px, 38%) minmax(420px, 1fr);
      min-height: calc(100vh - 48px);
    }}
    aside, section.workspace {{
      padding: 12px;
    }}
    aside {{
      border-right: 1px solid var(--line);
      background: #fbfcfd;
    }}
    .toolbar {{
      display: grid;
      grid-template-columns: 1fr 112px 44px;
      gap: 8px;
      margin-bottom: 10px;
    }}
    input, select, button {{
      height: 34px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      color: var(--text);
      padding: 0 10px;
      font: inherit;
    }}
    button.primary {{
      border-color: var(--accent);
      background: var(--accent);
      color: white;
      font-weight: 600;
    }}
    button:disabled {{
      color: #798390;
      background: #eef1f5;
      border-color: #d8dde5;
      cursor: not-allowed;
    }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 10px;
      margin-bottom: 10px;
    }}
    .comic-title {{
      font-weight: 700;
      font-size: 16px;
      margin-bottom: 4px;
    }}
    .muted, .empty {{ color: var(--muted); }}
    .meta-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
    }}
    .split {{
      display: grid;
      grid-template-columns: minmax(320px, 1fr) minmax(320px, 1fr);
      gap: 12px;
      align-items: start;
    }}
    h2 {{
      font-size: 16px;
      margin: 0 0 10px;
    }}
    h3 {{
      font-size: 14px;
      margin: 0 0 8px;
    }}
    .table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    .table th, .table td {{
      border-bottom: 1px solid var(--line);
      padding: 7px 6px;
      text-align: left;
      vertical-align: top;
    }}
    .status {{
      display: inline-flex;
      align-items: center;
      height: 22px;
      padding: 0 8px;
      border-radius: 999px;
      background: #eef6f1;
      color: var(--ok);
      font-size: 12px;
      font-weight: 600;
    }}
    .status.planned {{
      background: var(--accent-soft);
      color: var(--warn);
    }}
    .chapter-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(82px, 1fr));
      gap: 8px 12px;
      margin: 8px 0 12px;
    }}
    .chapter-grid label {{
      display: flex;
      align-items: center;
      gap: 6px;
      min-width: 0;
    }}
    .chapter-grid input {{
      width: 16px;
      height: 16px;
      padding: 0;
    }}
    .queue-tabs {{
      display: flex;
      gap: 8px;
      margin-bottom: 8px;
    }}
    .queue-tabs span {{
      padding: 6px 8px;
      border-bottom: 2px solid transparent;
      color: var(--muted);
    }}
    .queue-tabs span:first-child {{
      color: var(--accent);
      border-color: var(--accent);
    }}
    code {{
      display: block;
      overflow-x: auto;
      padding: 8px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #f9fafb;
    }}
    .settings-grid {{
      display: grid;
      grid-template-columns: 150px 1fr;
      gap: 8px;
      align-items: center;
    }}
    @media (max-width: 860px) {{
      main, .split {{
        grid-template-columns: 1fr;
      }}
      aside {{
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }}
      .chapter-grid {{
        grid-template-columns: repeat(2, minmax(90px, 1fr));
      }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="brand">PanelScout 格探</div>
    <nav aria-label="Primary">
{nav}
    </nav>
  </header>
  <main>
    <aside id="search">
      <form class="toolbar" aria-label="Search toolbar">
        <input type="search" value="{_e(search_value)}" aria-label="Search keyword">
        <select aria-label="Source">
          <option>{_e(ui_state.source)}</option>
        </select>
        <button class="primary" type="button">Search</button>
      </form>
{_render_search_cards(ui_state)}
      <div class="card" id="local-library">
        <h2>Local Library</h2>
        <table class="table">
          <thead><tr><th>Title</th><th>Latest</th><th>Checked</th></tr></thead>
          <tbody>
{_render_library_rows(ui_state)}
          </tbody>
        </table>
      </div>
    </aside>
    <section class="workspace">
      <div class="split">
{_render_detail(ui_state)}
{_render_watchlist(ui_state)}
      </div>
      <div class="split">
{_render_update_history(ui_state)}
{_render_downloads(ui_state, use_fallback_preview=use_fallback_preview)}
      </div>
{_render_settings(ui_state)}
    </section>
  </main>
</body>
</html>
"""


def write_local_ui_shell(output_path: str | Path, state: LocalUiState | None = None) -> Path:
    path = Path(output_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_local_ui_shell(state), encoding="utf-8")
    return path


def _render_search_cards(state: LocalUiState) -> str:
    if not state.comics:
        return f"""      <div class="card">
        <div class="comic-title">No local catalog data yet</div>
        <p class="empty">{_e(state.data_status)}</p>
      </div>"""
    return "\n".join(_render_comic_card(comic) for comic in state.comics[:6])


def _render_comic_card(comic: UiComic) -> str:
    return f"""      <div class="card">
        <div class="comic-title">{_e(comic.title)}</div>
        <div class="meta-row">
{_render_comic_meta(comic, include_source_id=True)}
        </div>
      </div>"""


def _render_library_rows(state: LocalUiState) -> str:
    if not state.comics:
        return '            <tr><td colspan="3" class="empty">No comics in local library yet.</td></tr>'
    rows = []
    for comic in state.comics[:20]:
        checked = comic.last_checked_at or comic.updated_at or "never"
        latest = comic.latest_chapter_title or "unknown"
        rows.append(
            "            "
            f"<tr><td>{_e(comic.title)}</td><td>{_e(latest)}</td><td>{_e(checked)}</td></tr>"
        )
    return "\n".join(rows)


def _render_detail(state: LocalUiState) -> str:
    comic = state.selected_comic
    if comic is None:
        return """        <div class="card">
          <h2>Comic Detail</h2>
          <div class="comic-title">No comic selected</div>
          <p class="empty">Save public metadata first to populate this panel.</p>
          <h3>Local Chapters</h3>
          <p class="empty">No chapters for the selected comic yet.</p>
          <button type="button" disabled>Sync Detail - planned</button>
          <button type="button" disabled>Add Watch - planned</button>
        </div>"""

    detail_url = comic.detail_url or "unknown"
    summary = f'          <p class="muted">{_e(comic.summary)}</p>\n' if comic.summary else ""
    return f"""        <div class="card">
          <h2>Comic Detail</h2>
          <div class="comic-title">{_e(comic.title)}</div>
          <div class="meta-row">
{_render_comic_meta(comic, include_source_id=True)}
          </div>
          <p class="muted">Detail URL: {_e(detail_url)}</p>
{summary}          <h3>Local Chapters</h3>
{_render_detail_chapters(state)}
          <button type="button" disabled>Sync Detail - planned</button>
          <button type="button" disabled>Add Watch - planned</button>
        </div>"""


def _render_detail_chapters(state: LocalUiState) -> str:
    if not state.chapters:
        return '          <p class="empty">No local chapters saved for this comic yet.</p>'
    rows = []
    for index, chapter in enumerate(state.chapters[:12], start=1):
        order = chapter.chapter_order if chapter.chapter_order is not None else index
        rows.append(
            "              "
            f"<tr><td>{_e(order)}</td><td>{_e(chapter.title)}</td>"
            f"<td>{_e(chapter.chapter_url)}</td></tr>"
        )
    return f"""          <table class="table" aria-label="Selected comic chapters">
            <thead><tr><th>Order</th><th>Chapter</th><th>Chapter URL</th></tr></thead>
            <tbody>
{chr(10).join(rows)}
            </tbody>
          </table>"""


def _render_watchlist(state: LocalUiState) -> str:
    rows = []
    if not state.watchlist_entries:
        rows.append(
            '              <tr><td colspan="4" class="empty">No watched comics yet.</td></tr>'
        )
    else:
        for entry in state.watchlist_entries[:20]:
            checked = entry.last_checked_at or "never"
            notes = entry.notes or "none"
            status_class = "status" if entry.last_checked_at else "status planned"
            status_text = "ready" if entry.last_checked_at else "planned check"
            rows.append(
                "              "
                f"<tr><td>{_e(entry.comic.title)}</td><td>{_e(checked)}</td><td>{_e(notes)}</td>"
                f'<td><span class="{status_class}">{status_text}</span></td></tr>'
            )
    body = "\n".join(rows)
    return f"""        <div class="card" id="watchlist">
          <h2>Watchlist</h2>
          <table class="table">
            <thead><tr><th>Comic</th><th>Last checked</th><th>Notes</th><th>Status</th></tr></thead>
            <tbody>
{body}
            </tbody>
          </table>
        </div>"""


def _render_update_history(state: LocalUiState) -> str:
    rows = []
    if not state.history_rows:
        rows.append(
            '              <tr><td colspan="3" class="empty">No local update history yet.</td></tr>'
        )
    else:
        for row in state.history_rows:
            rows.append(
                "              "
                f"<tr><td>{_e(row.kind)}</td><td>{_e(row.comic_title)}</td>"
                f"<td>{_e(row.detail)}</td></tr>"
            )
    schedule = state.watch_schedule
    if schedule is None:
        schedule_line = "No local watch schedule configured."
    else:
        enabled = "enabled" if schedule.enabled else "disabled"
        schedule_line = (
            f"{schedule.source}: every {schedule.interval_minutes} minutes, "
            f"{enabled}, next run {schedule.next_run_at}"
        )
    return f"""        <div class="card" id="update-history">
          <h2>Update History</h2>
          <p><strong>Database:</strong> {_e(state.data_status)}</p>
          <p><strong>Watch schedule:</strong> {_e(schedule_line)}</p>
          <table class="table">
            <thead><tr><th>Type</th><th>Comic</th><th>Detail</th></tr></thead>
            <tbody>
{chr(10).join(rows)}
            </tbody>
          </table>
        </div>"""


def _render_downloads(state: LocalUiState, *, use_fallback_preview: bool) -> str:
    if state.chapters:
        chapter_controls = "\n".join(
            f'            <label><input type="checkbox">{_e(chapter.title)}</label>'
            for chapter in state.chapters[:12]
        )
    else:
        chapter_controls = '            <p class="empty">No local chapters available yet.</p>'
    preview = DOWNLOAD_LAYOUT_PREVIEW if use_fallback_preview else _download_preview(state)
    return f"""        <div class="card" id="downloads">
          <h2>Downloads</h2>
          <div class="queue-tabs" aria-label="Download queue tabs">
            <span>Pending</span><span>Completed</span><span>Failed</span>
          </div>
          <h3>Chapter Selector</h3>
          <div class="chapter-grid">
{chapter_controls}
          </div>
          <button type="button" disabled>Download selected chapters - planned</button>
          <button type="button" disabled>Retry failed - planned</button>
          <p class="muted">Queue status: planned only; no downloader engine is active in Unit 16.</p>
          <h3>Folder Preview</h3>
          <code>{_e(preview)}</code>
        </div>"""


def _render_settings(state: LocalUiState) -> str:
    return f"""      <div class="card" id="settings">
        <h2>Settings</h2>
        <div class="settings-grid">
          <label for="database-path">Database path</label>
          <input id="database-path" value="{_e(state.database_path)}">
          <label for="download-root">Download root</label>
          <input id="download-root" value="~/PanelScout Downloads">
          <label for="concurrency">Download concurrency</label>
          <input id="concurrency" value="1" disabled>
          <label for="rate-limit">Rate limit</label>
          <input id="rate-limit" value="1 request every 3 seconds" disabled>
        </div>
        <p><span class="status planned">Downloader controls planned/disabled</span></p>
      </div>"""


def _render_comic_meta(comic: UiComic, *, include_source_id: bool) -> str:
    parts = []
    if comic.author:
        parts.append(f"author: {comic.author}")
    if comic.latest_chapter_title:
        parts.append(f"latest: {comic.latest_chapter_title}")
    if comic.status:
        parts.append(f"status: {comic.status}")
    if include_source_id:
        parts.append(f"source id: {comic.source_comic_id}")
    if not parts:
        parts.append(f"source: {comic.source}")
    return "\n".join(f"          <span>{_e(part)}</span>" for part in parts)


def _download_preview(state: LocalUiState) -> str:
    if state.selected_comic is None:
        return DOWNLOAD_LAYOUT_PREVIEW
    comic_name = _path_segment(state.selected_comic.title, fallback="漫画名")
    chapter_name = (
        _path_segment(state.chapters[0].title, fallback="001话")
        if state.chapters
        else "001话"
    )
    return f"download_root/{comic_name}/{chapter_name}/001.jpg"


def _path_segment(value: str, *, fallback: str) -> str:
    cleaned = value.strip().replace("/", "_").replace("\\", "_")
    return cleaned or fallback


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _anchor(label: str) -> str:
    return label.lower().replace(" ", "-")
