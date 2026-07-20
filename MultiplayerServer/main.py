from __future__ import annotations
import asyncio
import logging
from typing import Dict, Tuple

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from config import DB_PATH, RECONNECT_GRACE_SECONDS
from core.bus import AsyncMessageBus
from core.clock import RealClock
from core.protocol import ErrorCode, Envelope, encode
from db.connection import Database
from db.matches_repository import MatchesRepository
from db.schema import init_schema
from db.users_repository import UsersRepository
from game.results import record_match_result
from game.rooms import RoomManager
from matchmaking.matchmaker_loop import MatchmakerLoop
from matchmaking.queue import MatchmakingQueue
from network.dispatch import build_dispatcher
from network.server import SessionManager, make_handler
from network.session import ClientSession, Role
from observability.logging_conf import configure_logging
from resilience.reconnect_loop import ReconnectLoop
from resilience.reconnect_state import ReconnectState

HOST = '0.0.0.0'
PORT = 8765


async def run(host: str = HOST, port: int = PORT, db_path: str = DB_PATH) -> None:
    """
    Composition root: builds every sub-package's objects, wires them
    together, serves forever. Nothing else in the codebase should call
    serve() or construct a SessionManager/Bus/Database/RoomManager/
    MatchmakerLoop/ReconnectLoop.

    Phase 5 removed the Phase 1-4 single-match-slot limit: RoomManager can
    run many concurrent Rooms. room_players tracks each active room's
    (white_user_id, black_user_id) — recorded at pairing/creation time,
    since on_game_over must not re-derive it by looking up sessions by
    role: a disconnect-timeout resignation's loser has already been
    removed from session_manager by the time their game ends.
    """
    configure_logging()

    db = Database(db_path)
    await db.run(init_schema)
    users_repo = UsersRepository(db)
    matches_repo = MatchesRepository(db)

    bus = AsyncMessageBus()
    session_manager = SessionManager()
    matchmaking_queue = MatchmakingQueue(clock=RealClock())
    reconnect_state = ReconnectState(clock=RealClock(), grace_seconds=RECONNECT_GRACE_SECONDS)

    room_players: Dict[str, Tuple[int, int]] = {}

    async def on_game_over(room_id: str, winner_role: Role, loser_role: Role, reason: str) -> None:
        white_user_id, black_user_id = room_players.pop(room_id, (None, None))

        await record_match_result(
            users_repo, matches_repo,
            white_user_id=white_user_id, black_user_id=black_user_id,
            white_won=(winner_role is Role.WHITE),
            result_reason=reason,
        )

        # Clear any lingering reconnect entry (e.g. the game ended by
        # capture while the eventual loser was mid-disconnect).
        if white_user_id is not None:
            reconnect_state.reclaim(white_user_id)
        if black_user_id is not None:
            reconnect_state.reclaim(black_user_id)

        # Whoever is still connected in this room (players or viewers)
        # goes back to unmatched; a disconnected participant's session no
        # longer exists in session_manager at all.
        for session in session_manager.sessions:
            if session.room_id == room_id:
                session.role, session.room_id = None, None

        # Scheduled, not awaited: this callback can run from inside the
        # room's own tick-loop coroutine (the king-capture path), which
        # can't cancel and await itself (§3.2). resign()'s call path has
        # no such constraint, but using the same safe pattern
        # unconditionally is simpler than special-casing it.
        asyncio.create_task(room_manager.end_room(room_id))

    room_manager = RoomManager(bus, session_manager, on_game_over=on_game_over)

    async def on_paired(white_user_id: int, black_user_id: int) -> None:
        white = session_manager.get_by_user_id(white_user_id)
        black = session_manager.get_by_user_id(black_user_id)
        if white is None or black is None:
            return  # one of them disconnected while queued — drop the pairing

        room = room_manager.create_room()
        room_players[room.room_id] = (white_user_id, black_user_id)
        white.role, white.room_id = Role.WHITE, room.room_id
        black.role, black.room_id = Role.BLACK, room.room_id
        await white.websocket.send(encode(Envelope(type='match_found', data={'role': 'white', 'room_id': room.room_id})))
        await black.websocket.send(encode(Envelope(type='match_found', data={'role': 'black', 'room_id': room.room_id})))
        room.start()

    async def on_queue_timeout(user_id: int) -> None:
        session = session_manager.get_by_user_id(user_id)
        if session is not None:
            await session.websocket.send(encode(Envelope(type='error', data={'code': ErrorCode.QUEUE_TIMEOUT.value})))

    async def on_disconnect(session: ClientSession) -> None:
        if session.role is None or session.room_id is None or session.user_id is None:
            return  # never made it into a room — nothing to preserve
        reconnect_state.mark_disconnected(session.user_id, session.role, session.room_id)

        for other in session_manager.sessions:
            if other.room_id != session.room_id or other is session:
                continue
            try:
                await other.websocket.send(encode(Envelope(
                    type='opponent_disconnected', data={'grace_seconds': RECONNECT_GRACE_SECONDS},
                )))
            except ConnectionClosed:
                pass

    async def on_reconnect_expired(_user_id: int, role: Role, room_id: str) -> None:
        room = room_manager.get(room_id)
        if room is not None:
            await room.resign(role, 'disconnect_timeout')

    matchmaker = MatchmakerLoop(matchmaking_queue, RealClock(), on_paired, on_queue_timeout)
    reconnect_loop = ReconnectLoop(reconnect_state, RealClock(), on_reconnect_expired)

    handler = make_handler(
        session_manager,
        on_message=build_dispatcher(room_manager, session_manager, users_repo, matchmaking_queue, reconnect_state),
        on_disconnect=on_disconnect,
    )

    matchmaker.start()
    reconnect_loop.start()
    try:
        async with serve(handler, host, port) as server:
            logging.getLogger(__name__).info('listening on %s:%s', host, port)
            await server.serve_forever()
    finally:
        await matchmaker.stop()
        await reconnect_loop.stop()
        for room in list(room_manager.rooms):
            await room_manager.end_room(room.room_id)
        await db.close()


if __name__ == '__main__':
    asyncio.run(run())
