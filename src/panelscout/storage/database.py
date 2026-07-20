"""SQLite database connection and schema initialization."""

from __future__ import annotations

from pathlib import Path
import sqlite3

SCHEMA_VERSION = 3

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS comics (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    source_comic_id TEXT NOT NULL,
    title TEXT NOT NULL,
    author TEXT,
    status TEXT,
    audience TEXT,
    categories TEXT NOT NULL DEFAULT '[]',
    tags TEXT NOT NULL DEFAULT '[]',
    summary TEXT,
    latest_chapter_title TEXT,
    detail_url TEXT,
    cover_url TEXT,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_checked_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source, source_comic_id)
);

CREATE INDEX IF NOT EXISTS idx_comics_title ON comics(title);
CREATE INDEX IF NOT EXISTS idx_comics_source ON comics(source);
CREATE INDEX IF NOT EXISTS idx_comics_updated_at ON comics(updated_at);

CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY,
    comic_id INTEGER NOT NULL,
    source_chapter_id TEXT,
    title TEXT NOT NULL,
    chapter_order INTEGER,
    chapter_url TEXT NOT NULL,
    published_hint TEXT,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (comic_id) REFERENCES comics(id) ON DELETE CASCADE,
    UNIQUE (comic_id, chapter_url)
);

CREATE INDEX IF NOT EXISTS idx_chapters_comic_id ON chapters(comic_id);
CREATE INDEX IF NOT EXISTS idx_chapters_order ON chapters(comic_id, chapter_order);

CREATE TABLE IF NOT EXISTS watchlist_entries (
    id INTEGER PRIMARY KEY,
    comic_id INTEGER NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_checked_at TEXT,
    notes TEXT,
    FOREIGN KEY (comic_id) REFERENCES comics(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_watchlist_entries_created_at
    ON watchlist_entries(created_at);
CREATE INDEX IF NOT EXISTS idx_watchlist_entries_last_checked_at
    ON watchlist_entries(last_checked_at);

CREATE TABLE IF NOT EXISTS watch_check_schedules (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL UNIQUE,
    interval_minutes INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_run_at TEXT,
    next_run_at TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_watch_check_schedules_next_run_at
    ON watch_check_schedules(enabled, next_run_at);

CREATE TABLE IF NOT EXISTS crawl_jobs (
    id INTEGER PRIMARY KEY,
    job_type TEXT NOT NULL,
    source TEXT NOT NULL,
    query TEXT,
    status TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_crawl_jobs_status ON crawl_jobs(status);
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_source ON crawl_jobs(source);

CREATE TABLE IF NOT EXISTS crawl_logs (
    id INTEGER PRIMARY KEY,
    job_id INTEGER,
    url TEXT NOT NULL,
    status_code INTEGER,
    fetched_at TEXT NOT NULL,
    parser_status TEXT,
    error_message TEXT,
    FOREIGN KEY (job_id) REFERENCES crawl_jobs(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_crawl_logs_job_id ON crawl_logs(job_id);
CREATE INDEX IF NOT EXISTS idx_crawl_logs_url ON crawl_logs(url);

CREATE TABLE IF NOT EXISTS auth_sessions (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL UNIQUE,
    storage_backend TEXT NOT NULL,
    session_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_validated_at TEXT,
    expires_hint TEXT,
    status TEXT NOT NULL,
    warning_acknowledged_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_status ON auth_sessions(status);

INSERT OR IGNORE INTO schema_migrations(version) VALUES (1);
INSERT OR IGNORE INTO schema_migrations(version) VALUES (2);
INSERT OR IGNORE INTO schema_migrations(version) VALUES (3);
"""


def connect_database(
    database_path: str | Path,
    *,
    initialize: bool = True,
) -> sqlite3.Connection:
    """Open a SQLite database and optionally initialize the PanelScout schema."""

    if str(database_path) != ":memory:":
        path = Path(database_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        database_name = str(path)
    else:
        database_name = ":memory:"

    connection = sqlite3.connect(database_name)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    if initialize:
        initialize_schema(connection)

    return connection


def initialize_schema(connection: sqlite3.Connection) -> None:
    """Create the SQLite schema required by the metadata storage baseline."""

    connection.executescript(SCHEMA_SQL)
    connection.commit()
