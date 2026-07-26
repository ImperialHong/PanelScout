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
      --chip: #eef3f8;
      --ok: #127a45;
      --bad: #aa2d2d;
      --warn: #9a5a00;
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
      min-width: 0;
      padding: 0 16px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }}
    header strong {{ min-width: 128px; flex: 0 0 auto; }}
    nav {{ display: flex; flex: 1 1 auto; min-width: 0; gap: 6px; overflow-x: auto; }}
    nav a {{
      color: var(--text);
      text-decoration: none;
      padding: 12px 10px 10px;
      border-bottom: 2px solid transparent;
      white-space: nowrap;
    }}
    nav a:first-child {{ color: var(--accent); border-color: var(--accent); }}
    .session-toggle {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin-left: auto;
      color: var(--muted);
      flex: 0 0 auto;
      white-space: nowrap;
    }}
    .session-toggle input {{
      min-height: 16px;
      width: 16px;
      padding: 0;
    }}
    main {{
      display: grid;
      grid-template-columns: minmax(330px, 38%) minmax(460px, 1fr);
      min-height: calc(100vh - 48px);
      align-items: start;
    }}
    aside, .workspace {{ min-width: 0; padding: 12px; }}
    .workspace {{ display: grid; gap: 12px; align-content: start; }}
    aside {{ border-right: 1px solid var(--line); background: #fbfcfd; }}
    .toolbar, .download-grid {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      margin-bottom: 10px;
    }}
    .download-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    #download .download-grid {{ grid-template-columns: 1fr; }}
    input, select, button {{
      min-width: 0;
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
      min-width: 0;
    }}
    .workspace .card {{ margin-bottom: 0; }}
    .card-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 10px;
    }}
    h2 {{ font-size: 16px; margin: 0 0 10px; }}
    .card-header h2 {{ margin: 0; }}
    h3 {{ font-size: 14px; margin: 0 0 8px; }}
    .muted, .empty {{ color: var(--muted); }}
    .badge {{
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 0 8px;
      border-radius: 999px;
      background: var(--chip);
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
      white-space: nowrap;
    }}
    .list {{ display: grid; gap: 8px; }}
    .comic {{
      width: 100%;
      text-align: left;
      background: var(--panel);
      border: 1px solid var(--line);
    }}
    .comic.selected {{
      border-color: var(--accent);
      background: var(--soft);
      box-shadow: inset 3px 0 0 var(--accent);
    }}
    .comic strong, .comic span, td {{ overflow-wrap: anywhere; }}
    .comic strong {{ display: block; font-size: 15px; }}
    .split {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 12px;
      align-items: start;
      min-width: 0;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 7px 6px; text-align: left; vertical-align: top; }}
    .chapter-list {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(118px, 1fr));
      gap: 8px;
      max-height: 320px;
      overflow: auto;
      padding-right: 2px;
    }}
    .chapter-list label {{
      display: flex;
      align-items: center;
      gap: 6px;
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      padding: 6px 8px;
    }}
    .chapter-list label.selected {{ border-color: var(--accent); background: var(--soft); }}
    .chapter-list input {{ min-height: 16px; width: 16px; padding: 0; }}
    .action-row {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .status-ok {{ color: var(--ok); font-weight: 700; }}
    .status-bad {{ color: var(--bad); font-weight: 700; }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      gap: 8px;
      margin: 8px 0 10px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fbfcfd;
      padding: 8px;
      min-width: 0;
    }}
    .metric span {{ display: block; color: var(--muted); font-size: 12px; }}
    .metric strong {{ display: block; margin-top: 2px; font-size: 16px; }}
    .metric.bad strong {{ color: var(--bad); }}
    .metric.ok strong {{ color: var(--ok); }}
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
      .toolbar, .chapter-list, .download-grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 520px) {{
      header {{ gap: 8px; padding: 0 10px; }}
      header strong {{ min-width: auto; }}
      nav a {{ padding-inline: 8px; }}
      .session-toggle span {{ display: none; }}
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
    <label class="session-toggle" title="使用本机已保存的登录会话">
      <input id="auth-mode" type="checkbox" checked aria-label="使用登录会话">
      <span>登录会话</span>
    </label>
  </header>
  <main>
    <aside id="search">
      <form class="toolbar" id="search-form">
        <input id="search-query" type="search" value="{_e(search_value)}" aria-label="搜索关键词">
        <button class="primary" type="submit">搜索并保存</button>
      </form>
      <div class="card">
        <div class="card-header">
          <h2>搜索结果</h2>
          <span class="badge" id="search-count">0 项</span>
        </div>
        <div class="list" id="search-results"></div>
      </div>
      <div class="card" id="library">
        <div class="card-header">
          <h2>本地库</h2>
          <span class="badge" id="library-count">0 项</span>
        </div>
        <div class="list" id="library-list"></div>
      </div>
    </aside>
    <section class="workspace">
      <div class="split">
        <div class="card" id="detail">
          <div class="card-header">
            <h2>漫画详情</h2>
            <span class="badge" id="detail-badge">{_e(source_comic_id or "未选择")}</span>
          </div>
          <div class="download-grid">
            <input id="source-comic-id" value="{_e(source_comic_id)}" aria-label="来源漫画 ID">
            <button class="secondary" id="sync-button" type="button">同步详情</button>
          </div>
          <table>
            <tbody id="detail-table"></tbody>
          </table>
        </div>
        <div class="card">
          <div class="card-header">
            <h2>章节选择</h2>
            <span class="badge" id="chapter-count">0 话</span>
          </div>
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
          <div class="action-row">
            <button id="plan-button" type="button">规划下载</button>
            <button class="primary" id="run-button" type="button">确认下载</button>
            <button id="status-button" type="button">读取状态</button>
          </div>
        </div>
        <div class="card" id="status">
          <div class="card-header">
            <h2>运行状态</h2>
            <span class="badge" id="status-badge">就绪</span>
          </div>
          <p id="message" class="muted">本地服务已就绪。</p>
          <div class="summary-grid" id="summary"></div>
          <pre id="output"></pre>
        </div>
      </div>
    </section>
  </main>
  <script>
    const state = {{
      selectedChapter: {_json_string(first_chapter)},
      selectedComicId: {_json_string(source_comic_id)},
      busy: false
    }};

    function showMessage(text, ok = true) {{
      const node = document.getElementById('message');
      node.textContent = text;
      node.className = ok ? 'status-ok' : 'status-bad';
      document.getElementById('status-badge').textContent = ok ? '就绪' : '需要处理';
    }}

    function showOutput(value) {{
      renderSummary(value);
      document.getElementById('output').textContent = JSON.stringify(value, null, 2);
    }}

    function metric(label, value, tone = '') {{
      const node = document.createElement('div');
      node.className = tone ? `metric ${{tone}}` : 'metric';
      const labelNode = document.createElement('span');
      labelNode.textContent = label;
      const valueNode = document.createElement('strong');
      valueNode.textContent = String(value);
      node.appendChild(labelNode);
      node.appendChild(valueNode);
      return node;
    }}

    function renderSummary(value) {{
      const target = document.getElementById('summary');
      target.replaceChildren();
      if (!value) {{
        return;
      }}
      if (typeof value.saved_count !== 'undefined') {{
        target.appendChild(metric('已保存', value.saved_count, 'ok'));
        target.appendChild(metric('已跳过', value.skipped_count || 0));
        target.appendChild(metric('失败', value.failed_count || 0, value.failed_count ? 'bad' : ''));
        return;
      }}
      if (value.download_status) {{
        target.appendChild(metric('下载状态', value.download_status.label || value.download_status.state));
        target.appendChild(metric('已保存', value.download_status.saved_count || 0, 'ok'));
        target.appendChild(metric('部分文件', value.download_status.partial_count || 0));
        return;
      }}
      if (typeof value.images_discovered !== 'undefined') {{
        target.appendChild(metric('发现图片', value.images_discovered));
        target.appendChild(metric('规划文件', (value.items || []).length));
        return;
      }}
      if (Array.isArray(value.chapters)) {{
        target.appendChild(metric('章节数', value.chapters.length));
        target.appendChild(metric('新增', value.new_chapter_count || 0, 'ok'));
        target.appendChild(metric('已有', value.existing_chapter_count || 0));
        return;
      }}
      if (Array.isArray(value.comics)) {{
        target.appendChild(metric('漫画数', value.comics.length));
        target.appendChild(metric('已保存', value.persisted_count || 0, 'ok'));
        return;
      }}
      if (Array.isArray(value.state?.comics) || Array.isArray(value.comics)) {{
        const localComics = value.state?.comics || value.comics || [];
        const localChapters = value.state?.chapters || value.chapters || [];
        target.appendChild(metric('本地漫画', localComics.length));
        target.appendChild(metric('当前章节', localChapters.length));
      }}
    }}

    function currentChapter() {{
      return state.selectedChapter || document.querySelector('input[name="chapter"]:checked')?.value || '';
    }}

    function setBusy(isBusy, text = '') {{
      state.busy = isBusy;
      const badge = document.getElementById('status-badge');
      if (isBusy) {{
        badge.textContent = '运行中';
      }} else if (!document.getElementById('message').classList.contains('status-bad')) {{
        badge.textContent = '就绪';
      }}
      if (text) {{
        document.getElementById('message').textContent = text;
        document.getElementById('message').className = 'muted';
      }}
      updateControls();
    }}

    function updateControls() {{
      const hasComic = Boolean(document.getElementById('source-comic-id').value.trim());
      const hasChapter = Boolean(currentChapter());
      document.querySelector('#search-form button').disabled = state.busy;
      document.getElementById('sync-button').disabled = state.busy || !hasComic;
      document.getElementById('plan-button').disabled = state.busy || !hasComic || !hasChapter;
      document.getElementById('run-button').disabled = state.busy || !hasComic || !hasChapter;
      document.getElementById('status-button').disabled = state.busy || !hasComic || !hasChapter;
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

    function authPayload() {{
      return document.getElementById('auth-mode').checked ? {{ auth: true }} : {{}};
    }}

    function updateComicSelectionStyles() {{
      document.querySelectorAll('.comic').forEach(button => {{
        button.classList.toggle('selected', button.dataset.sourceComicId === state.selectedComicId);
      }});
    }}

    function comicButton(comic) {{
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'comic';
      button.dataset.sourceComicId = comic.source_comic_id;
      if (comic.source_comic_id === state.selectedComicId) {{
        button.classList.add('selected');
      }}
      const title = document.createElement('strong');
      title.textContent = comic.title;
      const meta = document.createElement('span');
      meta.className = 'muted';
      meta.textContent = `ID：${{comic.source_comic_id}}　最新：${{comic.latest_chapter_title || '未知'}}`;
      button.appendChild(title);
      button.appendChild(meta);
      button.addEventListener('click', () => {{
        state.selectedComicId = comic.source_comic_id;
        state.selectedChapter = '';
        document.getElementById('source-comic-id').value = comic.source_comic_id;
        renderDetail(comic, []);
        updateComicSelectionStyles();
      }});
      return button;
    }}

    function renderComics(comics, targetId) {{
      const target = document.getElementById(targetId);
      const countNode = document.getElementById(targetId === 'search-results' ? 'search-count' : 'library-count');
      if (countNode) {{
        countNode.textContent = `${{comics.length}} 项`;
      }}
      target.replaceChildren();
      if (!comics.length) {{
        const empty = document.createElement('p');
        empty.className = 'empty';
        empty.textContent = '暂无数据。';
        target.appendChild(empty);
        return;
      }}
      comics.forEach(comic => target.appendChild(comicButton(comic)));
      updateComicSelectionStyles();
    }}

    function renderDetail(comic, chapters) {{
      const rows = document.getElementById('detail-table');
      rows.replaceChildren();
      document.getElementById('detail-badge').textContent = comic ? comic.source_comic_id : '未选择';
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
      state.selectedComicId = comic.source_comic_id;
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
      updateComicSelectionStyles();
    }}

    function renderChapters(chapters) {{
      const target = document.getElementById('chapter-list');
      document.getElementById('chapter-count').textContent = `${{chapters.length}} 话`;
      target.replaceChildren();
      if (!chapters.length) {{
        state.selectedChapter = '';
        const empty = document.createElement('p');
        empty.className = 'empty';
        empty.textContent = '暂无本地章节。';
        target.appendChild(empty);
        updateControls();
        return;
      }}
      if (!chapters.some(chapter => chapter.title === state.selectedChapter)) {{
        state.selectedChapter = chapters[0].title;
      }}
      chapters.forEach(chapter => {{
        const label = document.createElement('label');
        const input = document.createElement('input');
        input.type = 'radio';
        input.name = 'chapter';
        input.value = chapter.title;
        input.checked = chapter.title === state.selectedChapter;
        label.className = input.checked ? 'selected' : '';
        input.addEventListener('change', () => {{
          state.selectedChapter = chapter.title;
          document.querySelectorAll('.chapter-list label').forEach(node => node.classList.remove('selected'));
          label.classList.add('selected');
          updateControls();
        }});
        label.appendChild(input);
        label.appendChild(document.createTextNode(chapter.title));
        target.appendChild(label);
      }});
      updateControls();
    }}

    async function refreshState(options = {{ showOutputPanel: true }}) {{
      const response = await fetch('/api/state');
      const data = await response.json();
      renderComics(data.state.comics || [], 'library-list');
      renderDetail(data.state.selected_comic, data.state.chapters || []);
      if (options.showOutputPanel) {{
        showOutput(data.state);
      }}
      updateControls();
    }}

    document.getElementById('search-form').addEventListener('submit', async event => {{
      event.preventDefault();
      setBusy(true, '正在搜索并保存。');
      try {{
        const data = await api('/api/search', {{
          query: document.getElementById('search-query').value,
          save: true,
          ...authPayload()
        }});
        renderComics(data.comics || [], 'search-results');
        showMessage('搜索已完成。');
        showOutput(data);
        await refreshState({{ showOutputPanel: false }});
      }} catch (error) {{
        showMessage(error.message, false);
      }} finally {{
        setBusy(false);
      }}
    }});

    document.getElementById('sync-button').addEventListener('click', async () => {{
      setBusy(true, '正在同步详情和章节。');
      try {{
        const data = await api('/api/sync', {{
          reference: document.getElementById('source-comic-id').value,
          save: true,
          ...authPayload()
        }});
        await refreshState({{ showOutputPanel: false }});
        renderDetail(data.comic, data.chapters || []);
        showMessage('详情同步已完成。');
        showOutput(data);
      }} catch (error) {{
        showMessage(error.message, false);
      }} finally {{
        setBusy(false);
      }}
    }});

    function downloadPayload() {{
      return {{
        source_comic_id: document.getElementById('source-comic-id').value,
        chapter: state.selectedChapter || document.querySelector('input[name="chapter"]:checked')?.value || '',
        output_root: document.getElementById('download-root').value,
        permission_note: document.getElementById('permission-note').value,
        ...authPayload()
      }};
    }}

    document.getElementById('plan-button').addEventListener('click', async () => {{
      setBusy(true, '正在规划下载。');
      try {{
        const data = await api('/api/download/plan', downloadPayload());
        showMessage('下载规划已完成。');
        showOutput(data);
      }} catch (error) {{
        showMessage(error.message, false);
      }} finally {{
        setBusy(false);
      }}
    }});

    document.getElementById('run-button').addEventListener('click', async () => {{
      setBusy(true, '正在下载图片。');
      try {{
        const data = await api('/api/download/run', downloadPayload());
        showMessage('下载任务已完成。', data.ok);
        showOutput(data);
      }} catch (error) {{
        showMessage(error.message, false);
      }} finally {{
        setBusy(false);
      }}
    }});

    document.getElementById('status-button').addEventListener('click', async () => {{
      setBusy(true, '正在读取本地下载状态。');
      try {{
        const data = await api('/api/download/status', downloadPayload());
        showMessage('状态已读取。');
        showOutput(data);
      }} catch (error) {{
        showMessage(error.message, false);
      }} finally {{
        setBusy(false);
      }}
    }});

    document.getElementById('source-comic-id').addEventListener('input', () => {{
      state.selectedComicId = document.getElementById('source-comic-id').value.trim();
      updateComicSelectionStyles();
      updateControls();
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
