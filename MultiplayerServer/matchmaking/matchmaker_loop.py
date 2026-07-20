"""
The only async code in matchmaking/ — polls queue.py's pure methods
roughly once a second and acts on the results: pairs waiting players and
notifies players whose wait timed out.

Phase 1-4 capped this at one pairing per poll (is_match_in_progress gated
it entirely) because only one match could exist for the whole process.
Phase 5's game/rooms.py::Room removed that limit — many rooms can run
concurrently — so this loop now pairs everyone it can each poll.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Awaitable, Callable, Optional

from core.clock import Clock
from matchmaking.queue import MatchmakingQueue

logger = logging.getLogger(__name__)

OnPaired = Callable[[int, int], Awaitable[None]]  # (white_user_id, black_user_id)
OnTimeout = Callable[[int], Awaitable[None]]  # (user_id)


class MatchmakerLoop:
    """start()/stop() mirror game/rooms.py::Room's — same teardown discipline (§3.2)."""

    def __init__(self, queue: MatchmakingQueue, clock: Clock, on_paired: OnPaired, on_timeout: OnTimeout,
                 poll_interval_seconds: float = 1.0):
        self._queue = queue
        self._clock = clock
        self._on_paired = on_paired
        self._on_timeout = on_timeout
        self._poll_interval_seconds = poll_interval_seconds
        self._task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        return self._task is not None

    def start(self) -> None:
        if self._task is not None:
            raise RuntimeError('MatchmakerLoop is already running')
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        task = self._task
        self._task = None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._poll_interval_seconds)
            await self._poll_once()

    async def _poll_once(self) -> None:
        now = self._clock.now()

        for user_id in self._queue.expire(now):
            await self._safe_call(self._on_timeout, user_id)

        for white_id, black_id in self._queue.find_pairings(now):
            await self._safe_call(self._on_paired, white_id, black_id)

    @staticmethod
    async def _safe_call(fn, *args) -> None:
        try:
            await fn(*args)
        except Exception:
            logger.exception('matchmaker callback raised')
