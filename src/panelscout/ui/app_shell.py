"""Interactive local UI shell served by the local runner."""

from __future__ import annotations

from html import escape
import json

from panelscout.ui.shell import DOWNLOAD_PERMISSION_NOTE
from panelscout.ui.state import LocalUiState


def build_interactive_ui_shell(state: LocalUiState) -> str:
    """Render the local runner UI.

    The page talks only to the local PanelScout HTTP runner. It does not call
    third-party websites directly and it does not start downloads on load.
    """

    selected = state.selected_comic
    search_value = selected.title if selected is not None else ""
    source_comic_id = selected.source_comic_id if selected is not None else ""
    first_chapter = state.chapters[0].title if state.chapters else ""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PanelScout 格探</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f6f8;
      --panel: #ffffff;
      --line: #d8dee8;
      --text: #17202a;
      --muted: #5f6b7a;
      --accent: #f06a00;
      --soft: #fff1e6;
      --ok: #127a45;
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
      height: 48px;
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 0 16px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }}
    header strong {{ min-width: 128px; }}
    nav {{ display: flex; gap: 6px; overflow-x: auto; }}
    nav a {{
      color: var(--text);
      text-decoration: none;
      padding: 12px 10px 10px;
      border-bottom: 2px solid transparent;
      white-space: nowrap;
    }}
    nav a:first-child {{ color: var(--accent); border-color: var(--accent); }}
    main {{
      display: grid;
      grid-template-columns: minmax(330px, 38%) minmax(460px, 1fr);
      min-height: calc(100vh - 48px);
    }}
    aside, .workspace {{ padding: 12px; }}
    aside {{ border-right: 1px solid var(--line); background: #fbfcfd; }}
    .toolbar, .download-grid {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      margin-bottom: 10px;
    }}
    .download-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    input, select, button {{
      min-height: 34px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      color: var(--text);
      padding: 0 10px;
      font: inherit;
    }}
    button {{
      cursor: pointer;
      font-weight: 600;
    }}
    button.primary {{ border-color: var(--accent); background: var(--accent); color: white; }}
    button.secondary {{ background: var(--soft); border-color: #f5c49b; }}
    button:disabled {{ cursor: not-allowed; opacity: 0.62; }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 10px;
      margin-bottom: 10px;
    }}
    h2 {{ font-size: 16px; margin: 0 0 10px; }}
    h3 {{ font-size: 14px; margin: 0 0 8px; }}
    .muted, .empty {{ color: var(--muted); }}
    .list {{ display: grid; gap: 8px; }}
    .comic {{
      width: 100%;
      text-align: left;
      background: var(--panel);
      border: 1px solid var(--line);
    }}
    .comic strong {{ display: block; font-size: 15px; }}
    .split {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 12px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 7px 6px; text-align: left; vertical-align: top; }}
    .chapter-list {{ display: grid; grid-template-columns: repeat(3, minmax(88px, 1fr)); gap: 8px; }}
    .chapter-list label {{ display: flex; align-items: center; gap: 6px; }}
    .chapter-list input {{ min-height: 16px; width: 16px; padding: 0; }}
    .status-ok {{ color: var(--ok); font-weight: 700; }}
    .status-bad {{ color: var(--bad); font-weight: 700; }}
    pre {{
      min-height: 96px;
      max-height: 240px;
      overflow: auto;
      white-space: pre-wrap;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #f9fafb;
      padding: 8px;
      font-size: 12px;
    }}
    @media (max-width: 900px) {{
      main, .split {{ grid-template-columns: 1fr; }}
      aside {{ border-right: 0; border-bottom: 1px solid var(--line); }}
      .chapter-list, .download-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <strong>PanelScout 格探</strong>
    <nav aria-label="主导航">
      <a href="#search">搜索</a>
      <a href="#library">本地库</a>
      <a href="#detail">详情</a>
      <a href="#download">下载</a>
      <a href="#status">状态</a>
    </nav>
  </header>
  <main>
    <aside id="search">
      <form class="toolbar" id="search-form">
        <input id="search-query" type="search" value="{_e(search_value)}" aria-label="搜索关键词">
        <button class="primary" type="submit">搜索并保存</button>
      </form>
      <div class="card">
        <h2>搜索结果</h2>
        <div class="list" id="search-results"></div>
      </div>
      <div class="card" id="library">
        <h2>本地库</h2>
        <div class="list" id="library-list"></div>
      </div>
    </aside>
    <section class="workspace">
      <div class="split">
        <div class="card" id="detail">
          <h2>漫画详情</h2>
          <div class="download-grid">
            <input id="source-comic-id" value="{_e(source_comic_id)}" aria-label="来源漫画 ID">
            <button class="secondary" id="sync-button" type="button">同步详情</button>
          </div>
          <table>
            <tbody id="detail-table"></tbody>
          </table>
        </div>
        <div class="card">
          <h2>章节选择</h2>
          <div class="chapter-list" id="chapter-list"></div>
        </div>
      </div>
      <div class="split">
        <div class="card" id="download">
          <h2>下载</h2>
          <div class="download-grid">
            <input id="download-root" value="{_e(state.download_root)}" aria-label="下载根目录">
            <input id="permission-note" value="{_e(DOWNLOAD_PERMISSION_NOTE)}" aria-label="权限确认">
          </div>
          <button id="plan-button" type="button">规划下载</button>
          <button class="primary" id="run-button" type="button">确认下载</button>
          <button id="status-button" type="button">读取状态</button>
        </div>
        <div class="card" id="status">
          <h2>运行状态</h2>
          <p id="message" class="muted">本地服务已就绪。</p>
          <pre id="output"></pre>
        </div>
      </div>
    </section>
  </main>
  <script>
    const state = {{
      selectedChapter: {_json_string(first_chapter)}
    }};

    function showMessage(text, ok = true) {{
      const node = document.getElementById('message');
      node.textContent = text;
      node.className = ok ? 'status-ok' : 'status-bad';
    }}

    function showOutput(value) {{
      document.getElementById('output').textContent = JSON.stringify(value, null, 2);
    }}

    async function api(path, body) {{
      const response = await fetch(path, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(body || {{}})
      }});
      const data = await response.json();
      if (!response.ok || data.ok === false) {{
        throw new Error(data.error || '请求失败');
      }}
      return data;
    }}

    function comicButton(comic) {{
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'comic';
      const title = document.createElement('strong');
      title.textContent = comic.title;
      const meta = document.createElement('span');
      meta.className = 'muted';
      meta.textContent = `ID：${{comic.source_comic_id}}　最新：${{comic.latest_chapter_title || '未知'}}`;
      button.appendChild(title);
      button.appendChild(meta);
      button.addEventListener('click', () => {{
        document.getElementById('source-comic-id').value = comic.source_comic_id;
        renderDetail(comic, []);
      }});
      return button;
    }}

    function renderComics(comics, targetId) {{
      const target = document.getElementById(targetId);
      target.replaceChildren();
      if (!comics.length) {{
        const empty = document.createElement('p');
        empty.className = 'empty';
        empty.textContent = '暂无数据。';
        target.appendChild(empty);
        return;
      }}
      comics.forEach(comic => target.appendChild(comicButton(comic)));
    }}

    function renderDetail(comic, chapters) {{
      const rows = document.getElementById('detail-table');
      rows.replaceChildren();
      if (!comic) {{
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.className = 'empty';
        cell.textContent = '尚未选择漫画。';
        row.appendChild(cell);
        rows.appendChild(row);
        renderChapters([]);
        return;
      }}
      [
        ['标题', comic.title],
        ['作者', comic.author || '未知'],
        ['最新', comic.latest_chapter_title || '未知'],
        ['地址', comic.detail_url || '未知']
      ].forEach(([label, value]) => {{
        const row = document.createElement('tr');
        const th = document.createElement('th');
        const td = document.createElement('td');
        th.textContent = label;
        td.textContent = value;
        row.appendChild(th);
        row.appendChild(td);
        rows.appendChild(row);
      }});
      renderChapters(chapters || []);
    }}

    function renderChapters(chapters) {{
      const target = document.getElementById('chapter-list');
      target.replaceChildren();
      if (!chapters.length) {{
        const empty = document.createElement('p');
        empty.className = 'empty';
        empty.textContent = '暂无本地章节。';
        target.appendChild(empty);
        return;
      }}
      chapters.forEach(chapter => {{
        const label = document.createElement('label');
        const input = document.createElement('input');
        input.type = 'radio';
        input.name = 'chapter';
        input.value = chapter.title;
        input.addEventListener('change', () => {{ state.selectedChapter = chapter.title; }});
        label.appendChild(input);
        label.appendChild(document.createTextNode(chapter.title));
        target.appendChild(label);
      }});
    }}

    async function refreshState() {{
      const response = await fetch('/api/state');
      const data = await response.json();
      renderComics(data.state.comics || [], 'library-list');
      renderDetail(data.state.selected_comic, data.state.chapters || []);
      showOutput(data.state);
    }}

    document.getElementById('search-form').addEventListener('submit', async event => {{
      event.preventDefault();
      try {{
        const data = await api('/api/search', {{
          query: document.getElementById('search-query').value,
          save: true
        }});
        renderComics(data.comics || [], 'search-results');
        showMessage('搜索已完成。');
        showOutput(data);
        await refreshState();
      }} catch (error) {{
        showMessage(error.message, false);
      }}
    }});

    document.getElementById('sync-button').addEventListener('click', async () => {{
      try {{
        const data = await api('/api/sync', {{
          reference: document.getElementById('source-comic-id').value,
          save: true
        }});
        renderDetail(data.comic, data.chapters || []);
        showMessage('详情同步已完成。');
        showOutput(data);
      }} catch (error) {{
        showMessage(error.message, false);
      }}
    }});

    function downloadPayload() {{
      return {{
        source_comic_id: document.getElementById('source-comic-id').value,
        chapter: state.selectedChapter || document.querySelector('input[name="chapter"]:checked')?.value || '',
        output_root: document.getElementById('download-root').value,
        permission_note: document.getElementById('permission-note').value
      }};
    }}

    document.getElementById('plan-button').addEventListener('click', async () => {{
      try {{
        const data = await api('/api/download/plan', downloadPayload());
        showMessage('下载规划已完成。');
        showOutput(data);
      }} catch (error) {{
        showMessage(error.message, false);
      }}
    }});

    document.getElementById('run-button').addEventListener('click', async () => {{
      try {{
        const data = await api('/api/download/run', downloadPayload());
        showMessage('下载任务已完成。', data.ok);
        showOutput(data);
      }} catch (error) {{
        showMessage(error.message, false);
      }}
    }});

    document.getElementById('status-button').addEventListener('click', async () => {{
      try {{
        const data = await api('/api/download/status', downloadPayload());
        showMessage('状态已读取。');
        showOutput(data);
      }} catch (error) {{
        showMessage(error.message, false);
      }}
    }});

    refreshState();
  </script>
</body>
</html>
"""


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _json_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)
