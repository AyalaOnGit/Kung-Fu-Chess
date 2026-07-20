"""
Phase 5's Room: generalizes Phase 1-4's game/match.py::MatchSession into
something addressable by room_id, with viewers, and true concurrency —
many Rooms can run at once, each with its own GameEngine/tick task/Bus
topic, instead of the single shared match slot Phases 1-4 were limited to.
MatchSession has been retired; Room fully replaces it (nothing kept using
the old single-slot model once real concurrency existed — see the
blueprint's Phase 5 notes for why keeping both would just be duplication).

RoomManager is deliberately the only strong-referencing owner of a Room at
any time (§3.2) — sessions hold a room_id, not a Room reference. It also
owns each room's Bus subscriptions (broadcaster + event logger), so
end_room can run the full §3.2 teardown sequence in one place: unsubscribe
both, stop the tick task, drop the Room from the owning dict.
"""
from __future__ import annotations
import game.engine_path  # noqa: F401  (must run before any kungfu_chess import)

import asyncio
import logging
import secrets
import time
from typing import Awaitable, Callable, Dict, List, Optional

from websockets.exceptions import ConnectionClosed

from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.model.piece import Color

from config import TICK_INTERVAL_MS
from core.bus import AsyncMessageBus, Unsubscribe
from core.protocol import Envelope, encode
from game.commands import HandleResult, handle_jump, handle_move
from game.engine_bridge import EngineEventRelay
from game.engine_factory import build_game_stack
from game.events import GameOver
from game.wire import to_wire
from network.session import ClientSession, Role
from network.server import SessionManager
from observability.logging_conf import make_room_event_logger

logger = logging.getLogger(__name__)

# (room_id, winner_role, loser_role, reason)
OnGameOver = Callable[[str, Role, Role, str], Awaitable[None]]

_ROOM_ID_ATTEMPTS = 10


def topic_for(room_id: str) -> str:
    return f'room:{room_id}'


class Room:
    """
    Owns one GameEngine and its background tick task, addressable by
    room_id. Same start()/stop() teardown discipline as Phase 1-4's
    MatchSession — a Room is not itself responsible for unsubscribing its
    Bus listeners (RoomManager owns those, since it's the one that created
    them); Room only owns the engine and the tick task.
    """

    def __init__(self, room_id: str, bus: AsyncMessageBus, engine: Optional[GameEngine] = None,
                 tick_interval_ms: int = TICK_INTERVAL_MS, on_game_over: Optional[OnGameOver] = None):
        self.room_id = room_id
        self._bus = bus
        self._topic = topic_for(room_id)
        self._tick_interval_ms = tick_interval_ms
        self._engine: GameEngine = engine if engine is not None else build_game_stack()
        self._relay = EngineEventRelay(self._engine, bus, self._topic)
        self._tick_task: Optional[asyncio.Task] = None
        self._on_game_over = on_game_over
        self._game_over_handled = False

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def engine(self) -> GameEngine:
        return self._engine

    @property
    def is_running(self) -> bool:
        return self._tick_task is not None

    def start(self) -> None:
        """Start the background tick task. Raises if already running."""
        if self._tick_task is not None:
            raise RuntimeError('Room is already running')
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
        return handle_move(session, self._engine, self._bus, self._topic, data)

    def handle_jump(self, session: ClientSession, data: dict) -> HandleResult:
        return handle_jump(session, self._engine, self._bus, self._topic, data)

    async def resign(self, loser_role: Role, reason: str) -> None:
        """
        End the room's game for a reason other than a king capture
        (disconnect timeout, explicit resignation, ...) — see
        game/match.py's original docstring for why force_game_over() alone
        can't be picked up by diff_snapshots.
        """
        if self._game_over_handled:
            return
        self._game_over_handled = True
        self._engine.force_game_over()
        winner_role = Role.BLACK if loser_role is Role.WHITE else Role.WHITE
        self._bus.publish(self._topic, GameOver(winner=Color[winner_role.name], loser=Color[loser_role.name]))
        await self._call_on_game_over(winner_role, loser_role, reason)

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
        if self._game_over_handled:
            return
        game_over = next((e for e in events if isinstance(e, GameOver)), None)
        if game_over is None:
            return
        self._game_over_handled = True
        await self._call_on_game_over(Role[game_over.winner.name], Role[game_over.loser.name], 'king_captured')

    async def _call_on_game_over(self, winner_role: Role, loser_role: Role, reason: str) -> None:
        if self._on_game_over is None:
            return
        try:
            await self._on_game_over(self.room_id, winner_role, loser_role, reason)
        except Exception:
            logger.exception('on_game_over callback raised for room %s', self.room_id)


def _build_room_broadcaster(bus: AsyncMessageBus, session_manager: SessionManager, room_id: str) -> Unsubscribe:
    """
    Fan every game event for room_id out to every session currently in
    that room — players AND viewers alike (a viewer can't move, but they
    still need to see the game). Unlike Phases 1-4's single shared match,
    role alone no longer identifies "is in the active match" once more
    than one room can be running at once — room_id is what scopes this.
    """
    topic = topic_for(room_id)

    async def handler(event) -> None:
        envelope_type, data = to_wire(event)
        raw = encode(Envelope(type=envelope_type, data=data))
        for session in session_manager.sessions:
            if session.room_id != room_id:
                continue
            try:
                await session.websocket.send(raw)
            except ConnectionClosed:
                pass  # the session's own connection handler will clean it up

    return bus.subscribe(topic, handler)


class RoomManager:
    """
    Owns every currently active Room. The only strong-referencing owner
    (§3.2) — sessions hold a room_id, not a Room reference. end_room runs
    the full teardown sequence (unsubscribe broadcaster + logger, stop the
    tick task, drop the Room) in one place, so "who is responsible for
    releasing this" stays unambiguous.
    """

    def __init__(self, bus: AsyncMessageBus, session_manager: SessionManager,
                 on_game_over: Optional[OnGameOver] = None, log_events: bool = True):
        self._bus = bus
        self._session_manager = session_manager
        self._on_game_over = on_game_over
        self._log_events = log_events
        self._rooms: Dict[str, Room] = {}
        self._unsubscribers: Dict[str, List[Unsubscribe]] = {}

    def create_room(self, engine: Optional[GameEngine] = None) -> Room:
        room_id = self._generate_room_id()
        room = Room(room_id, self._bus, engine=engine, on_game_over=self._on_game_over)
        self._rooms[room_id] = room

        unsubscribers = [_build_room_broadcaster(self._bus, self._session_manager, room_id)]
        if self._log_events:
            unsubscribers.append(self._bus.subscribe(room.topic, make_room_event_logger(room_id)))
        self._unsubscribers[room_id] = unsubscribers

        return room

    def get(self, room_id: str) -> Optional[Room]:
        return self._rooms.get(room_id)

    async def end_room(self, room_id: str) -> None:
        """Idempotent: ending an already-ended (or never-existing) room_id is a no-op."""
        room = self._rooms.pop(room_id, None)
        for unsubscribe in self._unsubscribers.pop(room_id, ()):
            unsubscribe()
        if room is not None:
            await room.stop()

    @property
    def rooms(self) -> List[Room]:
        return list(self._rooms.values())

    def _generate_room_id(self) -> str:
        for _ in range(_ROOM_ID_ATTEMPTS):
            candidate = secrets.token_urlsafe(4)
            if candidate not in self._rooms:
                return candidate
        raise RuntimeError(f'could not generate a unique room_id in {_ROOM_ID_ATTEMPTS} attempts')
