"""
sqlite3 connection factory. Nothing here is async.

sqlite3.Connection objects may only be used from the thread that created
them (check_same_thread=True, the default). A plain asyncio.to_thread call
uses the loop's shared default executor, which can pick a *different*
worker thread on every call — so Database instead owns a dedicated
single-worker executor and always connects (lazily, on first use) from
inside that one thread. Every repository call then runs on that same
thread, which is both what sqlite3 requires and gives free serialization
of concurrent repository calls with no extra lock needed.
"""
from __future__ import annotations
import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional, TypeVar

T = TypeVar('T')


class Database:
    """Owns one sqlite3.Connection and the single worker thread it lives on."""

    def __init__(self, path: str):
        self._path = path
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='db')
        self._conn: Optional[sqlite3.Connection] = None

    async def run(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        """Run fn(connection) on the dedicated db thread and await its result."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._run_sync, fn)

    def _run_sync(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        conn = self._connect_if_needed()
        return fn(conn)

    def _connect_if_needed(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute('PRAGMA foreign_keys = ON')
        return self._conn

    async def close(self) -> None:
        """Closes the connection on the thread that owns it, then stops that thread."""
        if self._conn is not None:
            await self.run(lambda conn: conn.close())
            self._conn = None
        self._executor.shutdown(wait=True)
