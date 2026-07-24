from __future__ import annotations
import asyncio
import logging
from typing import Callable, Optional

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from config import DB_PATH, RECONNECT_GRACE_SECONDS
from core.bus import AsyncMessageBus
from core.clock import RealClock
from core.protocol import ErrorCode, Envelope, Role, encode
from db.connection import Database
from db.matches_repository import MatchesRepository
from db.schema import init_schema
from db.users_repository import UsersRepository
from game.rating_service import record_match_result
from game.room_membership import RoomMembership
from game.rooms import RoomManager
from game.wire import state_sync_payload
from matchmaking.matchmaker_loop import MatchmakerLoop
from matchmaking.queue import MatchmakingQueue
from network.dispatch import build_dispatcher
from network.server import SessionManager, build_handler
from network.session import ClientSession
from observability.logging_conf import configure_logging
from resilience.reconnect_loop import ReconnectLoop
from resilience.reconnect_state import ReconnectState

HOST = '0.0.0.0'
PORT = 8765


async def run(host: str = HOST, port: int = PORT, db_path: str = DB_PATH,
              board_factory: Optional[Callable[[], object]] = None) -> None:
    """
    Composition root: builds every sub-package's objects, wires them
    together, serves forever. Nothing else in the codebase should call
    serve() or construct a SessionManager/Bus/Database/RoomManager/
    MatchmakerLoop/ReconnectLoop.

    Phase 5 removed the Phase 1-4 single-match-slot limit: RoomManager can
    run many concurrent Rooms. room_membership tracks each active room's
    (white_user_id, black_user_id) — recorded at pairing/creation time,
    since on_game_over must not re-derive it by looking up sessions by
    role: a disconnect-timeout resignation's loser has already been
    removed from session_manager by the time their game ends.

    board_factory: builds the starting board for every fresh room this
    process creates (both a manually created room and a matchmade one --
    both ultimately go through RoomManager.create_room(), which is where
    this is actually threaded to; see game/rooms.py). None (the default)
    means "use the real standard chess starting position" -- RoomManager
    itself owns that default so this module never has to import anything
    kungfu_chess-related just to spell it out (§1 in network/dispatch.py's
    docstring: "the only package that imports kungfu_chess is game/").
    Overriding it is dependency injection for tests that need a
    deterministic, non-standard board (e.g. a king-capture-in-one-move
    scenario) instead of patching game/engine_factory.py's internals.
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

    room_membership = RoomMembership()

    async def on_game_over(room_id: str, winner_role: Role, loser_role: Role, reason: str) -> None:
        white_user_id, black_user_id = room_membership.remove(room_id)

        rating_change = await record_match_result(
            users_repo, matches_repo,
            white_user_id=white_user_id, black_user_id=black_user_id,
            white_won=(winner_role is Role.WHITE),
            result_reason=reason,
        )

        # A separate direct send, not folded into the room's game_over
        # broadcast: the engine's GameOver event (winner/loser Color) is
        # published on the bus well before this callback ever touches the
        # database, so the ELO deltas simply aren't known yet at that point
        # -- game/wire.py's event translation has no reason to learn about
        # users_repo just for this. Both sessions get it if still connected;
        # a player who already disconnected has nothing to receive it into.
        if rating_change is not None:
            rating_envelope = encode(Envelope(type='rating_update', data={
                'white_elo_before': rating_change.white_elo_before, 'white_elo_after': rating_change.white_elo_after,
                'black_elo_before': rating_change.black_elo_before, 'black_elo_after': rating_change.black_elo_after,
            }))
            for user_id in (white_user_id, black_user_id):
                recipient = session_manager.get_by_user_id(user_id) if user_id is not None else None
                if recipient is not None:
                    try:
                        await recipient.websocket.send(rating_envelope)
                    except ConnectionClosed:
                        pass

        # Clear any lingering reconnect entry (e.g. the game ended by
        # capture while the eventual loser was mid-disconnect).
        if white_user_id is not None:
            reconnect_state.reclaim(white_user_id)
        if black_user_id is not None:
            reconnect_state.reclaim(black_user_id)

        async def _unmatch_and_end_room() -> None:
            # Deferred as its own task (not run inline) so the room's own
            # final broadcast -- published moments ago by the same tick
            # that triggered this callback (e.g. the king-capture's
            # move_accepted/piece_captured/piece_arrived/game_over batch)
            # -- gets a real chance to actually reach every session first.
            # game/rooms.py's broadcaster is a separate queued subscriber
            # task that filters recipients by session.room_id *at delivery
            # time*, not at publish time; clearing room_id inline here (as
            # this used to do) reliably beat that subscriber to the punch,
            # silently dropping the entire final event batch for every
            # session in the room. Running on a fresh task instead lets
            # whatever's already queued ahead of it (the broadcaster's
            # already-scheduled wakeup from that publish) run first.
            for session in session_manager.sessions:
                if session.room_id == room_id:
                    session.role, session.room_id = None, None
            await room_manager.end_room(room_id)

        # Scheduled, not awaited: this callback can run from inside the
        # room's own tick-loop coroutine (the king-capture path), which
        # can't cancel and await itself (§3.2). resign()'s call path has
        # no such constraint, but using the same safe pattern
        # unconditionally is simpler than special-casing it.
        asyncio.create_task(_unmatch_and_end_room())

    room_manager = RoomManager(bus, session_manager, on_game_over=on_game_over, board_factory=board_factory)

    async def on_paired(white_user_id: int, black_user_id: int) -> None:
        white = session_manager.get_by_user_id(white_user_id)
        black = session_manager.get_by_user_id(black_user_id)
        if white is None or black is None:
            return  # one of them disconnected while queued — drop the pairing

        white_user = await users_repo.get_by_id(white_user_id)
        black_user = await users_repo.get_by_id(black_user_id)

        room = room_manager.create_room()
        room_membership.add(room.room_id, white_user_id, black_user_id)
        white.role, white.room_id = Role.WHITE, room.room_id
        black.role, black.room_id = Role.BLACK, room.room_id
        state = state_sync_payload(room.engine)
        # Both players' username+elo ride along on match_found so the HUD can
        # show "Player1 (1200) vs Player2 (1215)" from the moment the game
        # screen opens, without a separate round-trip.
        common_data = {
            'room_id': room.room_id, 'state': state,
            'white_username': white_user.username, 'white_elo': white_user.elo,
            'black_username': black_user.username, 'black_elo': black_user.elo,
        }
        await white.websocket.send(encode(Envelope(type='match_found', data={**common_data, 'role': 'white'})))
        await black.websocket.send(encode(Envelope(type='match_found', data={**common_data, 'role': 'black'})))
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

    handler = build_handler(
        session_manager,
        on_message=build_dispatcher(room_manager, session_manager, users_repo, matchmaking_queue, reconnect_state,
                                     room_membership=room_membership),
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
