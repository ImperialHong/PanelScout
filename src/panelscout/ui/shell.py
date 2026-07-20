"""Static MVP4 local UI shell renderer."""

from __future__ import annotations

from html import escape
from pathlib import Path

from panelscout.ui.state import LocalUiState, UiComic, sample_local_ui_state


NAV_ITEMS = (
    "搜索",
    "本地库",
    "追更",
    "更新历史",
    "下载",
    "设置",
)

NAV_ANCHORS = {
    "搜索": "search",
    "本地库": "local-library",
    "追更": "watchlist",
    "更新历史": "update-history",
    "下载": "downloads",
    "设置": "settings",
}

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
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PanelScout 本地界面</title>
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
    <nav aria-label="主导航">
{nav}
    </nav>
  </header>
  <main>
    <aside id="search">
      <form class="toolbar" aria-label="搜索工具栏">
        <input type="search" value="{_e(search_value)}" aria-label="搜索关键词">
        <select aria-label="来源">
          <option>{_e(ui_state.source)}</option>
        </select>
        <button class="primary" type="button">搜索</button>
      </form>
{_render_search_cards(ui_state)}
      <div class="card" id="local-library">
        <h2>本地库</h2>
        <table class="table">
          <thead><tr><th>标题</th><th>最新章节</th><th>检查时间</th></tr></thead>
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
        <div class="comic-title">暂无本地漫画数据</div>
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
        return '            <tr><td colspan="3" class="empty">本地库暂未保存漫画。</td></tr>'
    rows = []
    for comic in state.comics[:20]:
        checked = comic.last_checked_at or comic.updated_at or "从未检查"
        latest = comic.latest_chapter_title or "未知"
        rows.append(
            "            "
            f"<tr><td>{_e(comic.title)}</td><td>{_e(latest)}</td><td>{_e(checked)}</td></tr>"
        )
    return "\n".join(rows)


def _render_detail(state: LocalUiState) -> str:
    comic = state.selected_comic
    if comic is None:
        return """        <div class="card">
          <h2>漫画详情</h2>
          <div class="comic-title">尚未选择漫画</div>
          <p class="empty">先保存公开元数据后，这里会显示详情。</p>
          <h3>本地章节</h3>
          <p class="empty">当前漫画暂无本地章节。</p>
          <button type="button" disabled>同步详情 - 规划中</button>
          <button type="button" disabled>加入追更 - 规划中</button>
        </div>"""

    detail_url = comic.detail_url or "未知"
    summary = f'          <p class="muted">{_e(comic.summary)}</p>\n' if comic.summary else ""
    return f"""        <div class="card">
          <h2>漫画详情</h2>
          <div class="comic-title">{_e(comic.title)}</div>
          <div class="meta-row">
{_render_comic_meta(comic, include_source_id=True)}
          </div>
          <p class="muted">详情地址：{_e(detail_url)}</p>
{summary}          <h3>本地章节</h3>
{_render_detail_chapters(state)}
          <button type="button" disabled>同步详情 - 规划中</button>
          <button type="button" disabled>加入追更 - 规划中</button>
        </div>"""


def _render_detail_chapters(state: LocalUiState) -> str:
    if not state.chapters:
        return '          <p class="empty">当前漫画尚未保存本地章节。</p>'
    rows = []
    for index, chapter in enumerate(state.chapters[:12], start=1):
        order = chapter.chapter_order if chapter.chapter_order is not None else index
        rows.append(
            "              "
            f"<tr><td>{_e(order)}</td><td>{_e(chapter.title)}</td>"
            f"<td>{_e(chapter.chapter_url)}</td></tr>"
        )
    return f"""          <table class="table" aria-label="选中漫画章节">
            <thead><tr><th>顺序</th><th>章节</th><th>章节地址</th></tr></thead>
            <tbody>
{chr(10).join(rows)}
            </tbody>
          </table>"""


def _render_watchlist(state: LocalUiState) -> str:
    rows = []
    if not state.watchlist_entries:
        rows.append(
            '              <tr><td colspan="4" class="empty">暂无追更漫画。</td></tr>'
        )
    else:
        for entry in state.watchlist_entries[:20]:
            checked = entry.last_checked_at or "从未检查"
            notes = entry.notes or "无备注"
            status_class = "status" if entry.last_checked_at else "status planned"
            status_text = "已检查" if entry.last_checked_at else "待检查"
            rows.append(
                "              "
                f"<tr><td>{_e(entry.comic.title)}</td><td>{_e(checked)}</td><td>{_e(notes)}</td>"
                f'<td><span class="{status_class}">{status_text}</span></td></tr>'
            )
    body = "\n".join(rows)
    return f"""        <div class="card" id="watchlist">
          <h2>追更</h2>
          <table class="table">
            <thead><tr><th>漫画</th><th>最后检查</th><th>备注</th><th>状态</th></tr></thead>
            <tbody>
{body}
            </tbody>
          </table>
        </div>"""


def _render_update_history(state: LocalUiState) -> str:
    rows = []
    if not state.history_rows:
        rows.append(
            '              <tr><td colspan="3" class="empty">暂无本地更新历史。</td></tr>'
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
        schedule_line = "尚未配置本地追更计划。"
    else:
        enabled = "已启用" if schedule.enabled else "已禁用"
        schedule_line = (
            f"{schedule.source}：每 {schedule.interval_minutes} 分钟，"
            f"{enabled}，下次检查 {schedule.next_run_at}"
        )
    return f"""        <div class="card" id="update-history">
          <h2>更新历史</h2>
          <p><strong>数据库：</strong>{_e(state.data_status)}</p>
          <p><strong>追更计划：</strong>{_e(schedule_line)}</p>
          <table class="table">
            <thead><tr><th>类型</th><th>漫画</th><th>详情</th></tr></thead>
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
        chapter_controls = '            <p class="empty">暂无可选本地章节。</p>'
    preview = DOWNLOAD_LAYOUT_PREVIEW if use_fallback_preview else _download_preview(state)
    return f"""        <div class="card" id="downloads">
          <h2>下载</h2>
          <div class="queue-tabs" aria-label="下载队列标签">
            <span>待处理</span><span>已完成</span><span>失败</span>
          </div>
          <h3>章节选择</h3>
          <div class="chapter-grid">
{chapter_controls}
          </div>
          <button type="button" disabled>下载选中章节 - 规划中</button>
          <button type="button" disabled>重试失败任务 - 规划中</button>
          <p class="muted">队列状态：仅作规划展示；当前单元未启用下载引擎。</p>
          <h3>目录预览</h3>
          <code>{_e(preview)}</code>
        </div>"""


def _render_settings(state: LocalUiState) -> str:
    return f"""      <div class="card" id="settings">
        <h2>设置</h2>
        <div class="settings-grid">
          <label for="database-path">数据库路径</label>
          <input id="database-path" value="{_e(state.database_path)}">
          <label for="download-root">下载根目录</label>
          <input id="download-root" value="~/PanelScout 下载">
          <label for="concurrency">下载并发数</label>
          <input id="concurrency" value="1" disabled>
          <label for="rate-limit">限速</label>
          <input id="rate-limit" value="每 3 秒 1 次请求" disabled>
        </div>
        <p><span class="status planned">下载控件规划中/已禁用</span></p>
      </div>"""


def _render_comic_meta(comic: UiComic, *, include_source_id: bool) -> str:
    parts = []
    if comic.author:
        parts.append(f"作者：{comic.author}")
    if comic.latest_chapter_title:
        parts.append(f"最新：{comic.latest_chapter_title}")
    if comic.status:
        parts.append(f"状态：{comic.status}")
    if include_source_id:
        parts.append(f"来源 ID：{comic.source_comic_id}")
    if not parts:
        parts.append(f"来源：{comic.source}")
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
    return NAV_ANCHORS.get(label, label.lower().replace(" ", "-"))
