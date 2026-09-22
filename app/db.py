import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from app.config import DATABASE_PATH, DEFAULT_SEARCH_URL


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


@contextmanager
def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
                url TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                company TEXT,
                location TEXT,
                salary TEXT,
                workplace TEXT,
                source TEXT,
                board_posted_label TEXT,
                board_posted_at TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                reviewed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                jobs_found INTEGER DEFAULT 0,
                new_jobs INTEGER DEFAULT 0,
                message TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_reviewed_at ON jobs(reviewed_at);
            CREATE INDEX IF NOT EXISTS idx_jobs_first_seen_at ON jobs(first_seen_at);
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(scans)")}
        if "trigger" not in columns:
            conn.execute("ALTER TABLE scans ADD COLUMN trigger TEXT")
        job_columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
        if "source" not in job_columns:
            conn.execute("ALTER TABLE jobs ADD COLUMN source TEXT")
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('search_url', ?)",
            (DEFAULT_SEARCH_URL,),
        )


def get_setting(key: str, default: str | None = None) -> str | None:
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row:
            return row["value"]
    return default


def set_setting(key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_search_url() -> str:
    return get_setting("search_url", DEFAULT_SEARCH_URL) or DEFAULT_SEARCH_URL


def start_scan(trigger: str = "unknown") -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO scans (started_at, status, trigger) VALUES (?, 'running', ?)",
            (utc_now_iso(), trigger),
        )
        return cursor.lastrowid


def finish_scan(
    scan_id: int,
    *,
    status: str,
    jobs_found: int = 0,
    new_jobs: int = 0,
    message: str | None = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE scans
            SET finished_at = ?, status = ?, jobs_found = ?, new_jobs = ?, message = ?
            WHERE id = ?
            """,
            (utc_now_iso(), status, jobs_found, new_jobs, message, scan_id),
        )


def upsert_jobs(jobs: list[dict[str, Any]]) -> int:
    now = utc_now_iso()
    new_count = 0

    with get_connection() as conn:
        for job in jobs:
            existing = conn.execute(
                "SELECT url, board_posted_at FROM jobs WHERE url = ?",
                (job["url"],),
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE jobs
                    SET title = ?, company = ?, location = ?, salary = ?, workplace = ?,
                        source = COALESCE(?, source), last_seen_at = ?
                    WHERE url = ?
                    """,
                    (
                        job["title"],
                        job.get("company"),
                        job.get("location"),
                        job.get("salary"),
                        job.get("workplace"),
                        job.get("source"),
                        now,
                        job["url"],
                    ),
                )
            else:
                board_posted_at = job.get("board_posted_at")
                conn.execute(
                    """
                    INSERT INTO jobs (
                        url, title, company, location, salary, workplace, source,
                        board_posted_label, board_posted_at,
                        first_seen_at, last_seen_at, reviewed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        job["url"],
                        job["title"],
                        job.get("company"),
                        job.get("location"),
                        job.get("salary"),
                        job.get("workplace"),
                        job.get("source"),
                        job.get("board_posted_label"),
                        board_posted_at,
                        now,
                        now,
                    ),
                )
                new_count += 1

    return new_count


def get_new_jobs() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT * FROM jobs
            WHERE reviewed_at IS NULL
            ORDER BY first_seen_at DESC
            """
        ).fetchall()


def get_saved_jobs() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT * FROM jobs
            ORDER BY first_seen_at DESC
            """
        ).fetchall()


def mark_reviewed(urls: list[str]) -> int:
    if not urls:
        return 0
    now = utc_now_iso()
    with get_connection() as conn:
        placeholders = ",".join("?" for _ in urls)
        cursor = conn.execute(
            f"UPDATE jobs SET reviewed_at = ? WHERE url IN ({placeholders})",
            [now, *urls],
        )
        return cursor.rowcount


def get_latest_scan() -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM scans ORDER BY id DESC LIMIT 1"
        ).fetchone()


def get_scans(limit: int = 100) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM scans ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
