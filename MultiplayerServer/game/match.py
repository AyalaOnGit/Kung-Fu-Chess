"""
Phase 1-4's MatchSession: exactly two slots (white, black), one GameEngine,
one tick task. No room ID, no spectator list — those exist only from
Phase 5 onward (game/rooms.py), which generalizes this class rather than
extending it.
"""
from __future__ import annotations
import game.engine_path  # noqa: F401  (must run before any kungfu_chess import)

import asyncio
import logging
import time
from typing import Awaitable, Callable, Optional

from kungfu_chess.engine.game_engine import GameEngine

from config import TICK_INTERVAL_MS
from core.bus import AsyncMessageBus
from game.commands import HandleResult, handle_jump, handle_move
from game.engine_bridge import EngineEventRelay
from game.engine_factory import build_game_stack
from game.events import GameOver
from network.session import ClientSession, Role

logger = logging.getLogger(__name__)

TOPIC = 'match'  # Phase 1 has exactly one match per process — no room ID to key on yet.

OnGameOver = Callable[[Role, Role], Awaitable[None]]  # (winner_role, loser_role)


class MatchSession:
    """
    Owns one GameEngine and its background tick task for the process's
    single match. start()/stop() are the teardown discipline §3.2 asks be
    exercised from Phase 1 on: whatever owns a tick task must be able to
    cancel it cleanly, leaving nothing dangling in asyncio.all_tasks().
    """

    def __init__(self, bus: AsyncMessageBus, engine: Optional[GameEngine] = None,
                 tick_interval_ms: int = TICK_INTERVAL_MS, on_game_over: Optional[OnGameOver] = None):
        self._bus = bus
        self._tick_interval_ms = tick_interval_ms
        self._engine: GameEngine = engine if engine is not None else build_game_stack()
        self._relay = EngineEventRelay(self._engine, bus, TOPIC)
        self._tick_task: Optional[asyncio.Task] = None
        self._on_game_over = on_game_over
        self._game_over_handled = False

    @property
    def engine(self) -> GameEngine:
        return self._engine

    @property
    def is_running(self) -> bool:
        return self._tick_task is not None

    def start(self) -> None:
        """Start the background tick task. Raises if already running."""
        if self._tick_task is not None:
            raise RuntimeError('MatchSession is already running')
        self._tick_task = asyncio.create_task(self._run_tick_loop())

    async def stop(self) -> None:
        """Cancel the tick task and wait for it to actually finish. Idempotent."""
        if self._tick_task is None:
            return
        task = self._tick_task
        self._tick_task = None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def handle_move(self, session: ClientSession, data: dict) -> HandleResult:
        return handle_move(session, self._engine, self._bus, TOPIC, data)

    def handle_jump(self, session: ClientSession, data: dict) -> HandleResult:
        return handle_jump(session, self._engine, self._bus, TOPIC, data)

    async def _run_tick_loop(self) -> None:
        last = time.monotonic()
        while True:
            await asyncio.sleep(self._tick_interval_ms / 1000)
            now = time.monotonic()
            elapsed_ms = int((now - last) * 1000)
            last = now
            self._engine.wait(elapsed_ms)
            events = self._relay.tick()
            await self._handle_game_over_if_present(events)

    async def _handle_game_over_if_present(self, events) -> None:
        if self._game_over_handled or self._on_game_over is None:
            return
        game_over = next((e for e in events if isinstance(e, GameOver)), None)
        if game_over is None:
            return
        self._game_over_handled = True
        try:
            await self._on_game_over(Role[game_over.winner.name], Role[game_over.loser.name])
        except Exception:
            logger.exception('on_game_over callback raised')
