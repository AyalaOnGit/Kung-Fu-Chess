"""Repository Pattern: async methods whose bodies run through Database.run —
callers never see sqlite3 or SQL."""
from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from typing import Optional

from db.connection import Database


@dataclass(frozen=True)
class UserRecord:
    id: int
    username: str
    password_hash: str
    password_salt: str
    elo: int


_COLUMNS = 'id, username, password_hash, password_salt, elo'


def _row_to_record(row: sqlite3.Row) -> UserRecord:
    return UserRecord(
        id=row['id'], username=row['username'],
        password_hash=row['password_hash'], password_salt=row['password_salt'],
        elo=row['elo'],
    )


class UsersRepository:
    def __init__(self, db: Database):
        self._db = db

    async def create(self, username: str, password_hash: str, password_salt: str) -> UserRecord:
        def _create(conn: sqlite3.Connection) -> UserRecord:
            cursor = conn.execute(
                'INSERT INTO users (username, password_hash, password_salt) VALUES (?, ?, ?)',
                (username, password_hash, password_salt),
            )
            conn.commit()
            row = conn.execute(f'SELECT {_COLUMNS} FROM users WHERE id = ?', (cursor.lastrowid,)).fetchone()
            return _row_to_record(row)

        return await self._db.run(_create)

    async def get_by_username(self, username: str) -> Optional[UserRecord]:
        def _get(conn: sqlite3.Connection) -> Optional[UserRecord]:
            row = conn.execute(f'SELECT {_COLUMNS} FROM users WHERE username = ?', (username,)).fetchone()
            return None if row is None else _row_to_record(row)

        return await self._db.run(_get)

    async def get_by_id(self, user_id: int) -> Optional[UserRecord]:
        def _get(conn: sqlite3.Connection) -> Optional[UserRecord]:
            row = conn.execute(f'SELECT {_COLUMNS} FROM users WHERE id = ?', (user_id,)).fetchone()
            return None if row is None else _row_to_record(row)

        return await self._db.run(_get)

    async def update_elo(self, user_id: int, new_elo: int) -> None:
        def _update(conn: sqlite3.Connection) -> None:
            conn.execute('UPDATE users SET elo = ? WHERE id = ?', (new_elo, user_id))
            conn.commit()

        await self._db.run(_update)
