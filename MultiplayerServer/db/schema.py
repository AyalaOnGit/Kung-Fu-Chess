"""CREATE TABLE statements, idempotent init."""
from __future__ import annotations
import sqlite3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    elo INTEGER NOT NULL DEFAULT 1200,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    white_user_id INTEGER NOT NULL REFERENCES users(id),
    black_user_id INTEGER NOT NULL REFERENCES users(id),
    winner_user_id INTEGER NOT NULL REFERENCES users(id),
    result_reason TEXT NOT NULL,
    white_elo_before INTEGER NOT NULL,
    black_elo_before INTEGER NOT NULL,
    white_elo_after INTEGER NOT NULL,
    black_elo_after INTEGER NOT NULL,
    ended_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Create both tables if they don't already exist. Safe to call every startup."""
    conn.executescript(_SCHEMA)
    conn.commit()
