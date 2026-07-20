"""
The only async code in matchmaking/ — polls queue.py's pure methods
roughly once a second and acts on the results: pairs waiting players
(if no match is currently in progress — Phase 1-4 has exactly one match
slot, per §5) and notifies players whose wait timed out.
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
IsMatchInProgress = Callable[[], bool]


class MatchmakerLoop:
    """start()/stop() mirror MatchSession's — same teardown discipline (§3.2)."""

    def __init__(self, queue: MatchmakingQueue, clock: Clock, on_paired: OnPaired, on_timeout: OnTimeout,
                 is_match_in_progress: IsMatchInProgress, poll_interval_seconds: float = 1.0):
        self._queue = queue
        self._clock = clock
        self._on_paired = on_paired
        self._on_timeout = on_timeout
        self._is_match_in_progress = is_match_in_progress
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

        if self._is_match_in_progress():
            return  # only one slot; leave everyone queued for the next poll

        for white_id, black_id in self._queue.find_pairings(now, max_pairs=1):
            await self._safe_call(self._on_paired, white_id, black_id)

    @staticmethod
    async def _safe_call(fn, *args) -> None:
        try:
            await fn(*args)
        except Exception:
            logger.exception('matchmaker callback raised')
