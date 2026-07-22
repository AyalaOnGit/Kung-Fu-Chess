"""
The only async code in resilience/ — polls reconnect_state.py's expire()
roughly once a second and triggers auto-resign for anyone whose grace
period ran out without reconnecting. Same start()/stop() teardown
discipline as game/rooms.py's Room and matchmaking/matchmaker_loop.py.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Awaitable, Callable, Optional

from core.clock import Clock
from core.protocol import Role
from resilience.reconnect_state import ReconnectState

logger = logging.getLogger(__name__)

OnExpired = Callable[[int, Role, str], Awaitable[None]]  # (user_id, role, room_id)


class ReconnectLoop:
    def __init__(self, state: ReconnectState, clock: Clock, on_expired: OnExpired,
                 poll_interval_seconds: float = 1.0):
        self._state = state
        self._clock = clock
        self._on_expired = on_expired
        self._poll_interval_seconds = poll_interval_seconds
        self._task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        return self._task is not None

    def start(self) -> None:
        if self._task is not None:
            raise RuntimeError('ReconnectLoop is already running')
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
            for user_id, role, room_id in self._state.expire(self._clock.now()):
                await self._safe_call(user_id, role, room_id)

    async def _safe_call(self, user_id: int, role: Role, room_id: str) -> None:
        try:
            await self._on_expired(user_id, role, room_id)
        except Exception:
            logger.exception('reconnect-expired callback raised')
