"""SQLite 状态:记录已处理文件(增量去重)与提取结果(重算 README 不重跑 LLM)。"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

_SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_files (
    path        TEXT PRIMARY KEY,
    mtime       REAL NOT NULL,
    line_count  INTEGER NOT NULL,
    processed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS extractions (
    date     TEXT PRIMARY KEY,
    payload  TEXT NOT NULL,
    sessions INTEGER,
    turns    INTEGER,
    updated_at TEXT NOT NULL
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    return conn


def is_file_unchanged(conn: sqlite3.Connection, path: str, mtime: float, line_count: int) -> bool:
    row = conn.execute(
        "SELECT mtime, line_count FROM processed_files WHERE path=?", (path,)
    ).fetchone()
    return row == (mtime, line_count)


def mark_processed(conn: sqlite3.Connection, path: str, mtime: float, line_count: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO processed_files(path, mtime, line_count, processed_at)
           VALUES(?,?,?,?)
           ON CONFLICT(path) DO UPDATE SET
             mtime=excluded.mtime,
             line_count=excluded.line_count,
             processed_at=excluded.processed_at""",
        (path, mtime, line_count, now),
    )
    conn.commit()


def save_extraction(
    conn: sqlite3.Connection, date: str, payload: dict, sessions: int, turns: int
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO extractions(date, payload, sessions, turns, updated_at)
           VALUES(?,?,?,?,?)
           ON CONFLICT(date) DO UPDATE SET
             payload=excluded.payload,
             sessions=excluded.sessions,
             turns=excluded.turns,
             updated_at=excluded.updated_at""",
        (date, json.dumps(payload, ensure_ascii=False), sessions, turns, now),
    )
    conn.commit()


def get_extraction(conn: sqlite3.Connection, date: str) -> dict | None:
    row = conn.execute("SELECT payload FROM extractions WHERE date=?", (date,)).fetchone()
    return json.loads(row[0]) if row else None


def has_extraction(conn: sqlite3.Connection, date: str) -> bool:
    return conn.execute("SELECT 1 FROM extractions WHERE date=?", (date,)).fetchone() is not None


def all_extractions(conn: sqlite3.Connection) -> Iterator[tuple[str, dict]]:
    for date, payload in conn.execute("SELECT date, payload FROM extractions ORDER BY date"):
        yield date, json.loads(payload)
