"""Same Repository pattern as users_repository.py, for match history/results."""
from __future__ import annotations
import sqlite3

from db.connection import Database


class MatchesRepository:
    def __init__(self, db: Database):
        self._db = db

    async def record_result(
        self, *, white_user_id: int, black_user_id: int, winner_user_id: int, result_reason: str,
        white_elo_before: int, black_elo_before: int, white_elo_after: int, black_elo_after: int,
    ) -> int:
        """Insert one finished-match row and return its id."""

        def _insert(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(
                '''INSERT INTO matches (
                    white_user_id, black_user_id, winner_user_id, result_reason,
                    white_elo_before, black_elo_before, white_elo_after, black_elo_after
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (white_user_id, black_user_id, winner_user_id, result_reason,
                 white_elo_before, black_elo_before, white_elo_after, black_elo_after),
            )
            conn.commit()
            return cursor.lastrowid

        return await self._db.run(_insert)
