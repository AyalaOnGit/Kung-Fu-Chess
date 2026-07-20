from __future__ import annotations
import asyncio
import logging
from typing import Optional

from websockets.asyncio.server import serve

from config import DB_PATH
from core.bus import AsyncMessageBus
from core.clock import RealClock
from core.protocol import ErrorCode, Envelope, encode
from db.connection import Database
from db.matches_repository import MatchesRepository
from db.schema import init_schema
from db.users_repository import UsersRepository
from game.match import TOPIC, MatchSession
from game.results import record_match_result
from matchmaking.matchmaker_loop import MatchmakerLoop
from matchmaking.queue import MatchmakingQueue
from network.dispatch import build_broadcaster, build_dispatcher
from network.server import SessionManager, make_handler
from network.session import Role

HOST = '0.0.0.0'
PORT = 8765


async def run(host: str = HOST, port: int = PORT, db_path: str = DB_PATH) -> None:
    """
    Composition root: builds every sub-package's objects, wires them
    together, serves forever. Nothing else in the codebase should call
    serve() or construct a SessionManager/Bus/Database/MatchmakerLoop.

    Phase 1-4 has exactly one match slot (§5): the matchmaker only pairs a
    new match once the current one has ended, tracked here as
    current_match (a plain local, not a class — nothing outside this
    function needs it; is_match_in_progress/on_paired/on_game_over close
    over it via `nonlocal`).
    """
    db = Database(db_path)
    await db.run(init_schema)
    users_repo = UsersRepository(db)
    matches_repo = MatchesRepository(db)

    bus = AsyncMessageBus()
    session_manager = SessionManager()
    matchmaking_queue = MatchmakingQueue(clock=RealClock())

    current_match: Optional[MatchSession] = None

    def is_match_in_progress() -> bool:
        return current_match is not None

    async def on_game_over(winner_role: Role, loser_role: Role) -> None:
        nonlocal current_match
        white = next((s for s in session_manager.sessions if s.role is Role.WHITE), None)
        black = next((s for s in session_manager.sessions if s.role is Role.BLACK), None)

        await record_match_result(
            users_repo, matches_repo,
            white_user_id=white.user_id if white else None,
            black_user_id=black.user_id if black else None,
            white_won=(winner_role is Role.WHITE),
            result_reason='king_captured',
        )

        finished_match = current_match
        current_match = None  # frees the slot immediately for the next pairing
        if white is not None:
            white.role = None
        if black is not None:
            black.role = None

        if finished_match is not None:
            # Scheduled, not awaited: this callback runs from inside
            # finished_match's own tick-loop coroutine, which can't cancel
            # and await itself (§3.2).
            asyncio.create_task(finished_match.stop())

    async def on_paired(white_user_id: int, black_user_id: int) -> None:
        nonlocal current_match
        white = session_manager.get_by_user_id(white_user_id)
        black = session_manager.get_by_user_id(black_user_id)
        if white is None or black is None:
            return  # one of them disconnected while queued — drop the pairing

        white.role, black.role = Role.WHITE, Role.BLACK
        current_match = MatchSession(bus, on_game_over=on_game_over)
        await white.websocket.send(encode(Envelope(type='match_found', data={'role': 'white'})))
        await black.websocket.send(encode(Envelope(type='match_found', data={'role': 'black'})))
        current_match.start()

    async def on_timeout(user_id: int) -> None:
        session = session_manager.get_by_user_id(user_id)
        if session is not None:
            await session.websocket.send(encode(Envelope(type='error', data={'code': ErrorCode.QUEUE_TIMEOUT.value})))

    matchmaker = MatchmakerLoop(matchmaking_queue, RealClock(), on_paired, on_timeout, is_match_in_progress)

    unsubscribe_broadcaster = build_broadcaster(bus, session_manager, TOPIC)
    handler = make_handler(
        session_manager,
        on_message=build_dispatcher(lambda: current_match, users_repo, matchmaking_queue),
    )

    matchmaker.start()
    try:
        async with serve(handler, host, port) as server:
            logging.getLogger(__name__).info('listening on %s:%s', host, port)
            await server.serve_forever()
    finally:
        unsubscribe_broadcaster()
        await matchmaker.stop()
        if current_match is not None:
            await current_match.stop()
        await db.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
