"""Static MVP4 local UI shell renderer."""

from __future__ import annotations

from pathlib import Path


NAV_ITEMS = (
    "Search",
    "Local Library",
    "Watchlist",
    "Update History",
    "Downloads",
    "Settings",
)

DOWNLOAD_LAYOUT_PREVIEW = "download_root/漫画名/001话/001.jpg"


def build_local_ui_shell() -> str:
    """Render the static MVP4 local UI shell.

    Unit 15 deliberately ships a plain HTML artifact instead of a live app server.
    Controls that imply downloading are visible for planning but disabled.
    """

    nav = "\n".join(
        f'        <a class="nav-item" href="#{_anchor(item)}">{item}</a>'
        for item in NAV_ITEMS
    )
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
    .muted {{ color: var(--muted); }}
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
        <input type="search" value="伪恋" aria-label="Search keyword">
        <select aria-label="Source">
          <option>zaimanhua</option>
        </select>
        <button class="primary" type="button">Search</button>
      </form>
      <div class="card">
        <div class="comic-title">伪恋同盟</div>
        <div class="meta-row">
          <span>author: 榊葵/绫乃</span>
          <span>latest: 第112话</span>
          <span>status: 已完结</span>
        </div>
      </div>
      <div class="card">
        <div class="comic-title">海贼同人短篇合集</div>
        <div class="meta-row">
          <span>author: sample</span>
          <span>latest: 第018话</span>
          <span>source id: 251780</span>
        </div>
      </div>
      <div class="card" id="local-library">
        <h2>Local Library</h2>
        <table class="table">
          <thead><tr><th>Title</th><th>Latest</th><th>Checked</th></tr></thead>
          <tbody>
            <tr><td>伪恋同盟</td><td>第112话</td><td>2026-07-20</td></tr>
            <tr><td>Broken Watch</td><td class="muted">unknown</td><td class="muted">never</td></tr>
          </tbody>
        </table>
      </div>
    </aside>
    <section class="workspace">
      <div class="split">
        <div class="card">
          <h2>Comic Detail</h2>
          <div class="comic-title">伪恋同盟</div>
          <div class="meta-row">
            <span>source: zaimanhua</span>
            <span>id: 15599</span>
            <span>latest: 第112话</span>
          </div>
          <p class="muted">Detail URL: https://manhua.zaimanhua.com/details/15599</p>
          <button type="button">Sync Detail</button>
          <button type="button">Add Watch</button>
        </div>
        <div class="card" id="watchlist">
          <h2>Watchlist</h2>
          <table class="table">
            <thead><tr><th>Comic</th><th>Last checked</th><th>Status</th></tr></thead>
            <tbody>
              <tr><td>伪恋同盟</td><td>2026-07-20</td><td><span class="status">ready</span></td></tr>
              <tr><td>海贼同人短篇合集</td><td class="muted">never</td><td><span class="status planned">planned check</span></td></tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="split">
        <div class="card" id="update-history">
          <h2>Update History</h2>
          <p><strong>Last watch check:</strong> checked 2, succeeded 1, failed 1.</p>
          <table class="table">
            <thead><tr><th>Type</th><th>Comic</th><th>Detail</th></tr></thead>
            <tbody>
              <tr><td>New chapter</td><td>伪恋同盟</td><td>第003话 重新开始</td></tr>
              <tr><td>Metadata</td><td>伪恋同盟</td><td>Latest chapter changed</td></tr>
              <tr><td>Report</td><td colspan="2">watch-check.md ready for export</td></tr>
            </tbody>
          </table>
        </div>
        <div class="card" id="downloads">
          <h2>Downloads</h2>
          <div class="queue-tabs" aria-label="Download queue tabs">
            <span>Pending</span><span>Completed</span><span>Failed</span>
          </div>
          <h3>Chapter Selector</h3>
          <div class="chapter-grid">
            <label><input type="checkbox">001话</label>
            <label><input type="checkbox">002话</label>
            <label><input type="checkbox">003话</label>
            <label><input type="checkbox">004话</label>
            <label><input type="checkbox">005话</label>
            <label><input type="checkbox">006话</label>
          </div>
          <button type="button" disabled>Download selected chapters - planned</button>
          <button type="button" disabled>Retry failed - planned</button>
          <p class="muted">Queue status: planned only; no downloader engine is active in Unit 15.</p>
          <h3>Folder Preview</h3>
          <code>{DOWNLOAD_LAYOUT_PREVIEW}</code>
        </div>
      </div>
      <div class="card" id="settings">
        <h2>Settings</h2>
        <div class="settings-grid">
          <label for="database-path">Database path</label>
          <input id="database-path" value="~/.local/share/panelscout/panelscout.sqlite3">
          <label for="download-root">Download root</label>
          <input id="download-root" value="~/PanelScout Downloads">
          <label for="concurrency">Download concurrency</label>
          <input id="concurrency" value="1" disabled>
          <label for="rate-limit">Rate limit</label>
          <input id="rate-limit" value="1 request every 3 seconds" disabled>
        </div>
        <p><span class="status planned">Downloader controls planned/disabled</span></p>
      </div>
    </section>
  </main>
</body>
</html>
"""


def write_local_ui_shell(output_path: str | Path) -> Path:
    path = Path(output_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_local_ui_shell(), encoding="utf-8")
    return path


def _anchor(label: str) -> str:
    return label.lower().replace(" ", "-")
