"""Interactive local UI shell served by the local runner."""

from __future__ import annotations

from html import escape
import json

from panelscout.ui.state import LocalUiState


def build_interactive_ui_shell(state: LocalUiState) -> str:
    """Render the local runner UI.

    The page talks only to the local PanelScout HTTP runner. It does not call
    third-party websites directly and it does not start downloads on load.
    """

    selected = state.selected_comic
    search_value = selected.title if selected is not None else ""
    source_comic_id = selected.source_comic_id if selected is not None else ""
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
    }}
    * {{ box-sizing: border-box; }}
    [hidden] {{ display: none !important; }}
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
    nav {{
      display: flex;
      flex: 1 1 auto;
      min-width: 0;
      gap: 6px;
      overflow-x: auto;
    }}
    .account {{
      position: relative;
      margin-left: auto;
      flex: 0 0 auto;
    }}
    .account-button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      max-width: 190px;
      white-space: nowrap;
    }}
    .account-button .account-label {{
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .account-popover {{
      position: absolute;
      top: 42px;
      right: 0;
      z-index: 20;
      width: min(300px, calc(100vw - 24px));
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: 0 16px 36px rgb(23 32 42 / 16%);
      padding: 10px;
    }}
    .account-popover form {{
      display: grid;
      gap: 8px;
    }}
    .account-popover input {{
      width: 100%;
    }}
    .account-actions {{
      display: flex;
      gap: 8px;
    }}
    .account-actions button {{
      flex: 1 1 0;
    }}
    .account-message {{
      margin: 2px 0 0;
      font-size: 12px;
    }}
    main {{
      display: grid;
      grid-template-columns: minmax(330px, 38%) minmax(460px, 1fr);
      min-height: calc(100vh - 48px);
      align-items: start;
    }}
    main.status-only {{ grid-template-columns: 1fr; }}
    main.status-only aside {{ display: none; }}
    aside, .workspace {{
      min-width: 0;
      padding: 12px;
    }}
    aside {{
      border-right: 1px solid var(--line);
      background: #fbfcfd;
    }}
    .workspace {{
      display: grid;
      gap: 12px;
      align-content: start;
    }}
    .side-view, .workspace-view {{ min-width: 0; }}
    .toolbar, .download-grid, .path-row {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      margin-bottom: 10px;
    }}
    .download-grid {{ grid-template-columns: 1fr; }}
    .path-row {{ margin-bottom: 0; }}
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
    input[type="hidden"] {{ display: none; }}
    button {{
      cursor: pointer;
      font-weight: 600;
    }}
    button.primary {{ border-color: var(--accent); background: var(--accent); color: white; }}
    button.secondary {{ background: var(--soft); border-color: #f5c49b; }}
    button:disabled {{ cursor: not-allowed; opacity: 0.62; }}
    nav button {{
      min-height: 48px;
      border: 0;
      border-bottom: 2px solid transparent;
      border-radius: 0;
      background: transparent;
      padding: 12px 10px 10px;
      white-space: nowrap;
    }}
    nav button.active {{ color: var(--accent); border-color: var(--accent); }}
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
    .badge.ok {{ color: var(--ok); }}
    .badge.bad {{ color: var(--bad); }}
    .list {{ display: grid; gap: 8px; }}
    .comic-card {{
      width: 100%;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 36px;
      gap: 8px;
      align-items: center;
      text-align: left;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
    }}
    .comic-card.selected {{
      border-color: var(--accent);
      background: var(--soft);
      box-shadow: inset 3px 0 0 var(--accent);
    }}
    .comic-summary {{ min-width: 0; }}
    .comic-summary strong, .comic-summary span {{ overflow-wrap: anywhere; }}
    .comic-summary strong {{ display: block; font-size: 15px; }}
    .icon-button {{
      width: 34px;
      height: 34px;
      min-height: 34px;
      display: inline-grid;
      place-items: center;
      padding: 0;
      border-color: #f5c49b;
      background: var(--soft);
      color: var(--accent);
    }}
    .icon-button svg {{
      width: 18px;
      height: 18px;
      stroke: currentColor;
    }}
    .download-shell {{
      display: grid;
      grid-template-columns: minmax(280px, 34%) minmax(420px, 1fr);
      gap: 12px;
      align-items: start;
    }}
    #download-setup[hidden] + #queue {{ grid-column: 1 / -1; }}
    .chapter-list {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(118px, 1fr));
      gap: 8px;
      max-height: 320px;
      overflow: auto;
      padding-right: 2px;
      margin-bottom: 10px;
    }}
    .chapter-tools {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
    }}
    .select-all {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 30px;
      color: var(--muted);
      font-weight: 600;
    }}
    .select-all input {{
      min-height: 16px;
      width: 16px;
      padding: 0;
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
    .chapter-list input {{
      min-height: 16px;
      width: 16px;
      padding: 0;
    }}
    .action-row {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .queue-list {{ display: grid; gap: 8px; }}
    .queue-item {{
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fbfcfd;
      padding: 8px;
      min-width: 0;
    }}
    .queue-item header {{
      height: auto;
      padding: 0;
      border: 0;
      background: transparent;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 6px;
    }}
    .queue-item strong, .queue-item p {{ overflow-wrap: anywhere; }}
    .queue-item p {{ margin: 4px 0 0; }}
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
      max-height: 420px;
      overflow: auto;
      white-space: pre-wrap;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #f9fafb;
      padding: 8px;
      font-size: 12px;
    }}
    @media (max-width: 900px) {{
      main {{
        display: block;
        min-height: 0;
      }}
      .download-shell {{ grid-template-columns: 1fr; }}
      aside {{
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }}
      .toolbar, .chapter-list, .download-grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 520px) {{
      header {{ gap: 8px; padding: 0 10px; }}
      header strong {{ min-width: auto; }}
      nav button {{ padding-inline: 8px; }}
      .account-button {{ max-width: 116px; padding-inline: 8px; }}
    }}
  </style>
</head>
<body>
  <header>
    <strong>PanelScout 格探</strong>
    <nav aria-label="主导航">
      <button class="nav-tab active" type="button" data-view="search">搜索</button>
      <button class="nav-tab" type="button" data-view="library">本地库</button>
      <button class="nav-tab" type="button" data-view="status">状态</button>
    </nav>
    <div class="account" id="account-menu">
      <button class="account-button" id="account-button" type="button" aria-expanded="false">
        <span class="account-label" id="account-label">登录</span>
      </button>
      <div class="account-popover" id="login-popover" hidden>
        <form id="login-form">
          <input id="login-username" autocomplete="username" placeholder="用户名" aria-label="用户名">
          <input id="login-password" type="password" autocomplete="current-password" placeholder="密码" aria-label="密码">
          <p class="muted account-message">仅保存本机会话，不保存密码。</p>
          <p id="login-message" class="account-message" hidden></p>
          <div class="account-actions">
            <button class="primary" id="login-submit" type="submit">登录</button>
            <button id="login-cancel" type="button">取消</button>
          </div>
        </form>
      </div>
      <div class="account-popover" id="account-popover" hidden>
        <p class="muted account-message" id="account-status">已登录</p>
        <button id="logout-button" type="button">退出登录</button>
      </div>
    </div>
  </header>
  <main id="app-main">
    <aside id="side-panel">
      <section class="side-view" id="search-view">
        <form class="toolbar" id="search-form">
          <input id="search-query" type="search" value="{_e(search_value)}" aria-label="搜索关键词">
          <button class="primary" type="submit">搜索并保存</button>
        </form>
        <div class="card">
          <div class="card-header">
            <h2>搜索结果</h2>
            <span class="badge" id="search-count">0 项</span>
          </div>
          <p id="search-message" class="muted" hidden></p>
          <div class="list" id="search-results"></div>
        </div>
      </section>
      <section class="side-view" id="library-view" hidden>
        <div class="card" id="library">
          <div class="card-header">
            <h2>本地库</h2>
            <span class="badge" id="library-count">0 项</span>
          </div>
          <div class="list" id="library-list"></div>
        </div>
      </section>
    </aside>
    <section class="workspace">
      <section class="workspace-view" id="workflow-view">
        <div class="download-shell">
          <div class="card" id="download-setup" hidden>
            <div class="card-header">
              <h2 id="download-title">下载准备</h2>
              <span class="badge" id="chapter-count">0 话</span>
            </div>
            <input id="source-comic-id" type="hidden" value="{_e(source_comic_id)}">
            <div class="chapter-tools" id="chapter-tools" hidden>
              <label class="select-all">
                <input id="select-all-chapters" type="checkbox">
                <span>全选</span>
              </label>
              <span class="badge" id="selected-chapter-count">0 已选</span>
            </div>
            <div class="chapter-list" id="chapter-list"></div>
            <div class="download-grid">
              <div class="path-row">
                <input id="download-root" value="{_e(state.download_root)}" aria-label="下载根目录">
                <button class="icon-button" id="browse-download-root" type="button" title="选择下载目录" aria-label="选择下载目录">
                  <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v1"></path>
                    <path d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7H3"></path>
                  </svg>
                </button>
              </div>
            </div>
            <div class="action-row">
              <button class="primary" id="run-button" type="button">加入队列</button>
            </div>
          </div>
          <div class="card" id="queue">
            <div class="card-header">
              <h2>下载队列</h2>
              <span class="badge" id="queue-count">0 条</span>
            </div>
            <div class="queue-list" id="queue-list"></div>
          </div>
        </div>
      </section>
      <section class="workspace-view" id="status-view" hidden>
        <div class="card" id="status">
          <div class="card-header">
            <h2>运行状态</h2>
            <span class="badge" id="status-badge">就绪</span>
          </div>
          <p id="message" class="muted">本地服务已就绪。</p>
          <div class="summary-grid" id="summary"></div>
          <pre id="output"></pre>
        </div>
      </section>
    </section>
  </main>
  <script>
    const state = {{
      selectedChapters: [],
      selectedComicId: {_json_string(source_comic_id)},
      selectedComic: null,
      chapters: [],
      queue: [],
      queuePollingTimer: null,
      busy: false,
      authBusy: false,
      authenticated: false,
      userId: ""
    }};

    function switchView(view) {{
      document.querySelectorAll('.nav-tab').forEach(button => {{
        button.classList.toggle('active', button.dataset.view === view);
      }});
      document.getElementById('search-view').hidden = view !== 'search';
      document.getElementById('library-view').hidden = view !== 'library';
      document.getElementById('workflow-view').hidden = view === 'status';
      document.getElementById('status-view').hidden = view !== 'status';
      document.getElementById('app-main').classList.toggle('status-only', view === 'status');
    }}

    function showMessage(text, ok = true) {{
      const node = document.getElementById('message');
      node.textContent = text;
      node.className = ok ? 'status-ok' : 'status-bad';
      document.getElementById('status-badge').textContent = ok ? '就绪' : '需要处理';
    }}

    function showSearchMessage(text, ok = true) {{
      const node = document.getElementById('search-message');
      node.hidden = !text;
      node.textContent = text || '';
      node.className = ok ? 'status-ok' : 'status-bad';
    }}

    function friendlyError(message) {{
      if (message.includes('auth session not configured')) {{
        return '登录会话未配置；请点击右上角登录按钮完成登录，或继续使用公开搜索。';
      }}
      if (message.includes('login did not reach authenticated page state')) {{
        return '登录未完成；请确认用户名、密码以及网站登录校验后重试。';
      }}
      if (message.includes('Playwright is not installed')) {{
        return '本地浏览器登录依赖未安装；请安装 Playwright 和 Chromium 后重试。';
      }}
      return message;
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

    function selectedChapters() {{
      const checked = Array.from(document.querySelectorAll('input[name="chapter"]:checked'))
        .map(input => input.value)
        .filter(Boolean);
      if (checked.length) {{
        state.selectedChapters = checked;
      }}
      return [...state.selectedChapters];
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
      const hasChapter = selectedChapters().length > 0;
      document.querySelector('#search-form button').disabled = state.busy;
      document.getElementById('browse-download-root').disabled = state.busy;
      document.getElementById('run-button').disabled = state.busy || !hasComic || !hasChapter;
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

    async function apiGet(path) {{
      const response = await fetch(path);
      const data = await response.json();
      if (!response.ok || data.ok === false) {{
        throw new Error(data.error || '请求失败');
      }}
      return data;
    }}

    function authPayload() {{
      return state.authenticated ? {{ auth: true }} : {{}};
    }}

    function hideAccountPopovers() {{
      document.getElementById('login-popover').hidden = true;
      document.getElementById('account-popover').hidden = true;
      document.getElementById('account-button').setAttribute('aria-expanded', 'false');
    }}

    function renderAccount() {{
      const label = document.getElementById('account-label');
      const button = document.getElementById('account-button');
      const accountStatus = document.getElementById('account-status');
      button.classList.toggle('secondary', state.authenticated);
      if (state.authenticated) {{
        const userId = state.userId || '已登录';
        label.textContent = state.userId ? `ID：${{userId}}` : userId;
        button.title = '账号信息';
        accountStatus.textContent = state.userId ? `用户ID：${{userId}}` : '已登录';
      }} else {{
        label.textContent = '登录';
        button.title = '登录';
        accountStatus.textContent = '未登录';
      }}
    }}

    function showLoginMessage(text, ok = true) {{
      const node = document.getElementById('login-message');
      node.hidden = !text;
      node.textContent = text || '';
      node.className = ok ? 'account-message status-ok' : 'account-message status-bad';
    }}

    function setAuthBusy(isBusy, text = '') {{
      state.authBusy = isBusy;
      document.getElementById('account-button').disabled = isBusy;
      document.getElementById('login-submit').disabled = isBusy;
      document.getElementById('login-cancel').disabled = isBusy;
      document.getElementById('logout-button').disabled = isBusy;
      if (text) {{
        showLoginMessage(text);
      }}
    }}

    async function refreshAuthStatus() {{
      try {{
        const data = await apiGet('/api/auth/status');
        const savedUserId = window.localStorage.getItem('panelscout_user_id') || '';
        state.authenticated = Boolean(data.authenticated);
        state.userId = state.authenticated ? savedUserId : '';
        if (!state.authenticated) {{
          window.localStorage.removeItem('panelscout_user_id');
        }}
        renderAccount();
      }} catch (error) {{
        state.authenticated = false;
        state.userId = '';
        renderAccount();
        showMessage(friendlyError(error.message), false);
      }}
    }}

    function updateComicSelectionStyles() {{
      document.querySelectorAll('.comic-card').forEach(card => {{
        card.classList.toggle('selected', card.dataset.sourceComicId === state.selectedComicId);
      }});
    }}

    function comicButton(comic) {{
      const card = document.createElement('article');
      card.className = 'comic-card';
      card.dataset.sourceComicId = comic.source_comic_id;
      if (comic.source_comic_id === state.selectedComicId) {{
        card.classList.add('selected');
      }}

      const summary = document.createElement('div');
      summary.className = 'comic-summary';
      const title = document.createElement('strong');
      title.textContent = comic.title;
      const meta = document.createElement('span');
      meta.className = 'muted';
      meta.textContent = `ID：${{comic.source_comic_id}}　最新：${{comic.latest_chapter_title || '未知'}}`;
      summary.appendChild(title);
      summary.appendChild(meta);

      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'icon-button';
      button.title = '准备下载';
      button.setAttribute('aria-label', `准备下载 ${{comic.title}}`);
      button.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><path d="M7 10l5 5 5-5"></path><path d="M12 15V3"></path></svg>';
      button.addEventListener('click', () => openDownloadSetup(comic));

      card.appendChild(summary);
      card.appendChild(button);
      return card;
    }}

    function renderComics(comics, targetId, emptyText = '暂无数据。') {{
      const target = document.getElementById(targetId);
      const countNode = document.getElementById(targetId === 'search-results' ? 'search-count' : 'library-count');
      if (countNode) {{
        countNode.textContent = `${{comics.length}} 项`;
      }}
      target.replaceChildren();
      if (!comics.length) {{
        const empty = document.createElement('p');
        empty.className = 'empty';
        empty.textContent = emptyText;
        target.appendChild(empty);
        return;
      }}
      comics.forEach(comic => target.appendChild(comicButton(comic)));
      updateComicSelectionStyles();
    }}

    function renderDownloadSetup(comic, chapters) {{
      const panel = document.getElementById('download-setup');
      panel.hidden = !comic;
      if (!comic) {{
        renderChapters([]);
        return;
      }}
      state.selectedComicId = comic.source_comic_id;
      state.selectedComic = comic;
      document.getElementById('source-comic-id').value = comic.source_comic_id;
      document.getElementById('download-title').textContent = comic.title;
      renderChapters(chapters || []);
      updateComicSelectionStyles();
    }}

    function renderChapters(chapters) {{
      const target = document.getElementById('chapter-list');
      const tools = document.getElementById('chapter-tools');
      document.getElementById('chapter-count').textContent = `${{chapters.length}} 话`;
      target.replaceChildren();
      tools.hidden = !chapters.length;
      if (!chapters.length) {{
        state.selectedChapters = [];
        const empty = document.createElement('p');
        empty.className = 'empty';
        empty.textContent = '暂无可选章节。';
        target.appendChild(empty);
        updateChapterSelectionState();
        updateControls();
        return;
      }}
      const availableTitles = chapters.map(chapter => chapter.title);
      state.selectedChapters = state.selectedChapters.filter(title => availableTitles.includes(title));
      if (!state.selectedChapters.length) {{
        state.selectedChapters = [chapters[0].title];
      }}
      chapters.forEach(chapter => {{
        const label = document.createElement('label');
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.name = 'chapter';
        input.value = chapter.title;
        input.checked = state.selectedChapters.includes(chapter.title);
        label.className = input.checked ? 'selected' : '';
        input.addEventListener('change', () => {{
          state.selectedChapters = selectedChapters();
          updateChapterSelectionState();
        }});
        label.appendChild(input);
        label.appendChild(document.createTextNode(chapter.title));
        target.appendChild(label);
      }});
      updateChapterSelectionState();
    }}

    function updateChapterSelectionState() {{
      const inputs = Array.from(document.querySelectorAll('input[name="chapter"]'));
      const checked = inputs.filter(input => input.checked);
      state.selectedChapters = checked.map(input => input.value);
      document.querySelectorAll('.chapter-list label').forEach(label => {{
        const input = label.querySelector('input[name="chapter"]');
        label.classList.toggle('selected', Boolean(input?.checked));
      }});
      const selectAll = document.getElementById('select-all-chapters');
      selectAll.checked = inputs.length > 0 && checked.length === inputs.length;
      selectAll.indeterminate = checked.length > 0 && checked.length < inputs.length;
      document.getElementById('selected-chapter-count').textContent = `${{checked.length}} 已选`;
      updateControls();
    }}

    function queueEntryFromJob(job) {{
      const complete = job.status === 'complete';
      const failed = job.status === 'failed';
      let detail = '';
      if (job.status === 'pending') {{
        detail = '等待后台下载';
      }} else if (job.status === 'running') {{
        detail = '正在保存图片';
      }} else if (typeof job.saved_count !== 'undefined' && job.saved_count !== null) {{
        detail = `保存 ${{job.saved_count || 0}}，跳过 ${{job.skipped_count || 0}}，失败 ${{job.failed_count || 0}}`;
      }} else if (job.error) {{
        detail = friendlyError(job.error);
      }}
      return {{
        id: job.id,
        title: job.comic_title || '未知漫画',
        chapter: job.chapter_title || '未选择章节',
        status: job.status_label || job.status || '已记录',
        ok: complete ? true : failed ? false : null,
        tone: complete ? 'ok' : failed ? 'bad' : '',
        detail,
        path: job.chapter_directory || job.output_root,
        time: job.created_at ? new Date(job.created_at).toLocaleTimeString() : ''
      }};
    }}

    function renderQueueSnapshot(queue) {{
      state.queue = (queue?.jobs || []).map(queueEntryFromJob);
      renderQueue();
    }}

    function queueHasActive(queue) {{
      return Boolean(queue?.summary?.active);
    }}

    function startQueuePolling() {{
      if (state.queuePollingTimer) {{
        return;
      }}
      state.queuePollingTimer = window.setInterval(refreshQueue, 1500);
    }}

    function stopQueuePolling() {{
      if (!state.queuePollingTimer) {{
        return;
      }}
      window.clearInterval(state.queuePollingTimer);
      state.queuePollingTimer = null;
    }}

    async function refreshQueue() {{
      try {{
        const data = await apiGet('/api/download/queue');
        renderQueueSnapshot(data.queue);
        if (queueHasActive(data.queue)) {{
          startQueuePolling();
        }} else {{
          stopQueuePolling();
        }}
      }} catch (error) {{
        stopQueuePolling();
      }}
    }}

    function renderQueue() {{
      const target = document.getElementById('queue-list');
      document.getElementById('queue-count').textContent = `${{state.queue.length}} 条`;
      target.replaceChildren();
      if (!state.queue.length) {{
        const empty = document.createElement('p');
        empty.className = 'empty';
        empty.textContent = '暂无下载记录。';
        target.appendChild(empty);
        return;
      }}
      state.queue.forEach(entry => {{
        const item = document.createElement('article');
        item.className = 'queue-item';
        const header = document.createElement('header');
        const title = document.createElement('strong');
        title.textContent = entry.title;
        const badge = document.createElement('span');
        const tone = entry.ok === false ? 'bad' : entry.tone;
        badge.className = tone ? `badge ${{tone}}` : 'badge';
        badge.textContent = entry.status || '已记录';
        header.appendChild(title);
        header.appendChild(badge);
        item.appendChild(header);
        [
          entry.chapter,
          entry.detail,
          entry.path,
          entry.time
        ].filter(Boolean).forEach(text => {{
          const line = document.createElement('p');
          line.className = 'muted';
          line.textContent = text;
          item.appendChild(line);
        }});
        target.appendChild(item);
      }});
    }}

    async function openDownloadSetup(comic) {{
      state.selectedChapters = [];
      state.chapters = [];
      renderDownloadSetup(comic, []);
      setBusy(true, `正在读取《${{comic.title}}》的章节。`);
      try {{
        const data = await api('/api/sync', {{
          reference: comic.source_comic_id,
          save: true,
          ...authPayload()
        }});
        state.chapters = data.chapters || [];
        renderDownloadSetup(data.comic, state.chapters);
        await refreshState({{ showOutputPanel: false }});
        showMessage('章节已载入。');
        showOutput(data);
      }} catch (error) {{
        showMessage(error.message, false);
      }} finally {{
        setBusy(false);
      }}
    }}

    async function refreshState(options = {{ showOutputPanel: true }}) {{
      const response = await fetch('/api/state');
      const data = await response.json();
      renderComics(data.state.comics || [], 'library-list');
      if (options.showOutputPanel) {{
        showOutput(data.state);
      }}
      updateControls();
    }}

    function downloadPayload(chapters) {{
      return {{
        source_comic_id: document.getElementById('source-comic-id').value,
        chapters,
        output_root: document.getElementById('download-root').value,
        ui_confirmed: true,
        ...authPayload()
      }};
    }}

    document.getElementById('search-form').addEventListener('submit', async event => {{
      event.preventDefault();
      setBusy(true, '正在搜索并保存。');
      showSearchMessage('正在搜索。');
      renderComics([], 'search-results', '正在等待搜索结果。');
      try {{
        const data = await api('/api/search', {{
          query: document.getElementById('search-query').value,
          save: true,
          ...authPayload()
        }});
        renderComics(data.comics || [], 'search-results');
        showSearchMessage(`搜索完成，找到 ${{(data.comics || []).length}} 项。`);
        showMessage('搜索已完成。');
        showOutput(data);
        await refreshState({{ showOutputPanel: false }});
      }} catch (error) {{
        const message = friendlyError(error.message);
        renderComics([], 'search-results');
        showSearchMessage(message, false);
        showMessage(message, false);
      }} finally {{
        setBusy(false);
      }}
    }});

    document.getElementById('browse-download-root').addEventListener('click', async () => {{
      setBusy(true, '请选择下载目录。');
      try {{
        const input = document.getElementById('download-root');
        const data = await api('/api/download/select-directory', {{
          initial: input.value
        }});
        if (data.selected && data.path) {{
          input.value = data.path;
          showMessage('下载目录已更新。');
        }} else {{
          showMessage('下载目录未更改。');
        }}
      }} catch (error) {{
        showMessage(friendlyError(error.message), false);
      }} finally {{
        setBusy(false);
      }}
    }});

    document.getElementById('select-all-chapters').addEventListener('change', event => {{
      const checked = event.target.checked;
      document.querySelectorAll('input[name="chapter"]').forEach(input => {{
        input.checked = checked;
      }});
      updateChapterSelectionState();
    }});

    document.getElementById('run-button').addEventListener('click', async () => {{
      const chapters = selectedChapters();
      if (!chapters.length) {{
        showMessage('请选择至少一话。', false);
        return;
      }}
      setBusy(true, chapters.length > 1 ? `正在加入 ${{chapters.length}} 话到队列。` : '正在加入下载队列。');
      try {{
        const data = await api('/api/download/enqueue', downloadPayload(chapters));
        renderQueueSnapshot(data.queue);
        if (queueHasActive(data.queue)) {{
          startQueuePolling();
        }}
        showOutput(data);
        showMessage(`已加入下载队列：${{data.queued_count}} 话。`);
      }} catch (error) {{
        showMessage(friendlyError(error.message), false);
      }} finally {{
        setBusy(false);
      }}
    }});

    document.getElementById('account-button').addEventListener('click', () => {{
      const loginPopover = document.getElementById('login-popover');
      const accountPopover = document.getElementById('account-popover');
      if (state.authenticated) {{
        const shouldOpen = accountPopover.hidden;
        hideAccountPopovers();
        accountPopover.hidden = !shouldOpen;
      }} else {{
        const shouldOpen = loginPopover.hidden;
        hideAccountPopovers();
        loginPopover.hidden = !shouldOpen;
        if (shouldOpen) {{
          showLoginMessage('');
          document.getElementById('login-username').focus();
        }}
      }}
      document.getElementById('account-button').setAttribute(
        'aria-expanded',
        String(!loginPopover.hidden || !accountPopover.hidden)
      );
    }});

    document.getElementById('login-cancel').addEventListener('click', () => {{
      hideAccountPopovers();
      showLoginMessage('');
    }});

    document.getElementById('login-form').addEventListener('submit', async event => {{
      event.preventDefault();
      setAuthBusy(true, '正在登录。');
      try {{
        const username = document.getElementById('login-username').value;
        const data = await api('/api/auth/login', {{
          username,
          password: document.getElementById('login-password').value
        }});
        state.authenticated = true;
        state.userId = data.user_id || username.trim();
        if (state.userId) {{
          window.localStorage.setItem('panelscout_user_id', state.userId);
        }}
        document.getElementById('login-password').value = '';
        hideAccountPopovers();
        renderAccount();
        showMessage('登录完成。');
      }} catch (error) {{
        const message = friendlyError(error.message);
        showLoginMessage(message, false);
        showMessage(message, false);
      }} finally {{
        setAuthBusy(false);
      }}
    }});

    document.getElementById('logout-button').addEventListener('click', async () => {{
      setAuthBusy(true);
      try {{
        await api('/api/auth/logout', {{}});
        state.authenticated = false;
        state.userId = '';
        window.localStorage.removeItem('panelscout_user_id');
        hideAccountPopovers();
        renderAccount();
        showMessage('已退出登录。');
      }} catch (error) {{
        showMessage(friendlyError(error.message), false);
      }} finally {{
        setAuthBusy(false);
      }}
    }});

    document.addEventListener('click', event => {{
      if (!document.getElementById('account-menu').contains(event.target)) {{
        hideAccountPopovers();
      }}
    }});

    document.querySelectorAll('.nav-tab').forEach(button => {{
      button.addEventListener('click', () => switchView(button.dataset.view));
    }});

    renderAccount();
    renderQueue();
    refreshAuthStatus();
    refreshQueue();
    refreshState();
  </script>
</body>
</html>
"""


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _json_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)
