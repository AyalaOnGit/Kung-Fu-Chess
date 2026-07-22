"""
Command Pattern: envelope['type'] -> registered async handler. Adding a
wire command means registering one function in _HANDLERS, never editing a
branch chain.

build_dispatcher routes an incoming raw message to game/rooms.py (via the
session's room_id, if any), auth/service.py, matchmaking/queue.py, or
resilience/reconnect_state.py, and returns the direct response for the
sender alone. Room-scoped broadcasting itself lives in game/rooms.py now
(RoomManager wires it per-room at create_room/end_room) — this module
used to own a single build_broadcaster for the one Phase 1-4 match slot,
but that doesn't generalize to "however many rooms happen to exist."

Every handler takes the same (session, ctx: DispatchContext, data) shape
even though most fields of ctx go unused by any given handler — this
bundle replaced a growing list of positional parameters (which had grown
across three phases: match, then +users_repo, then +matchmaking_queue,
then +reconnect_state) once that growth stopped being manageable as
separate arguments.

This module still never imports kungfu_chess directly — game/wire.py
(§1: "the only package that imports kungfu_chess is game/") does the
translation from game events/engine state to JSON-safe dicts.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, Optional, Tuple

from auth import service as auth_service
from core.protocol import ErrorCode, Envelope, MalformedEnvelopeError, Role, decode, encode
from db.users_repository import UsersRepository
from game.commands import HandleResult
from game.room_membership import RoomMembership
from game.rooms import RoomManager
from game.wire import state_sync_payload
from matchmaking.queue import MatchmakingQueue
from network.session import ClientSession
from network.server import SessionManager
from observability.logging_conf import log_command
from resilience.reconnect_state import ReconnectState

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DispatchContext:
    room_manager: RoomManager
    session_manager: SessionManager
    users_repo: UsersRepository
    matchmaking_queue: MatchmakingQueue
    reconnect_state: ReconnectState
    # Same RoomMembership main.py's on_game_over reads from to know who to
    # record a rated result for. Matchmade rooms populate it in on_paired;
    # create_room/join_room have to populate it here instead, since
    # dispatch.py is the only place that ever learns a manually-created
    # room's seats.
    room_membership: RoomMembership = field(default_factory=RoomMembership)


Handler = Callable[[ClientSession, DispatchContext, dict], Awaitable[Envelope]]


def _result_envelope(result: HandleResult) -> Envelope:
    if result.accepted:
        return Envelope(type='accepted', data={})
    return Envelope(type='error', data={'code': result.error.value})


def _error(code: ErrorCode) -> Envelope:
    return Envelope(type='error', data={'code': code.value})


async def _handle_ping(_session: ClientSession, _ctx: DispatchContext, _data: dict) -> Envelope:
    return Envelope(type='pong', data={})


async def _handle_move(session: ClientSession, ctx: DispatchContext, data: dict) -> Envelope:
    room = ctx.room_manager.get(session.room_id) if session.room_id is not None else None
    if room is None:
        return _error(ErrorCode.NOT_IN_A_MATCH)
    return _result_envelope(room.handle_move(session, data))


async def _handle_jump(session: ClientSession, ctx: DispatchContext, data: dict) -> Envelope:
    room = ctx.room_manager.get(session.room_id) if session.room_id is not None else None
    if room is None:
        return _error(ErrorCode.NOT_IN_A_MATCH)
    return _result_envelope(room.handle_jump(session, data))


def _credentials(data: dict):
    """Return (username, password) if both are non-empty strings, else None."""
    username, password = data.get('username'), data.get('password')
    if not isinstance(username, str) or not username or not isinstance(password, str) or not password:
        return None
    return username, password


async def _handle_check_username(_session: ClientSession, ctx: DispatchContext, data: dict) -> Envelope:
    """
    Reports whether a username is already registered, so a shell-style
    client can prompt "enter matching password" vs "choose a password"
    before asking for one. This doesn't newly expose anything a client
    couldn't already learn one round-trip earlier by just attempting
    'register' and reading back a username_taken error -- it's the same
    bit of information via a more direct question, not a wider one (see
    auth/service.py's login() docstring for the *separate*, still-intact
    guarantee: wrong-password vs no-such-user stays indistinguishable).
    """
    username = data.get('username')
    if not isinstance(username, str) or not username:
        return _error(ErrorCode.MALFORMED_COMMAND)

    existing = await ctx.users_repo.get_by_username(username)
    return Envelope(type='username_status', data={'username': username, 'exists': existing is not None})


async def _handle_register(session: ClientSession, ctx: DispatchContext, data: dict) -> Envelope:
    credentials = _credentials(data)
    if credentials is None:
        return _error(ErrorCode.MALFORMED_COMMAND)

    result = await auth_service.register(ctx.users_repo, *credentials)
    if not result.ok:
        return _error(ErrorCode(result.error))

    session.user_id, session.username = result.user.id, result.user.username
    return Envelope(type='registered', data={'username': result.user.username, 'elo': result.user.elo})


async def _handle_login(session: ClientSession, ctx: DispatchContext, data: dict) -> Envelope:
    credentials = _credentials(data)
    if credentials is None:
        return _error(ErrorCode.MALFORMED_COMMAND)

    result = await auth_service.login(ctx.users_repo, *credentials)
    if not result.ok:
        return _error(ErrorCode(result.error))

    session.user_id, session.username = result.user.id, result.user.username

    # Reconnection: re-login is how a client re-proves its identity — no
    # session tokens. If this user_id disconnected out of an active room
    # within the grace period, rebind them into it instead of the normal
    # login response.
    reclaimed = ctx.reconnect_state.reclaim(session.user_id)
    if reclaimed is not None:
        reclaimed_role, room_id = reclaimed
        room = ctx.room_manager.get(room_id)
        if room is not None:
            session.role, session.room_id = reclaimed_role, room_id
            # Session for reclaimed_role is now this session, so this also
            # picks up our own just-reclaimed identity; the opponent's seat
            # only resolves if they're still connected (None otherwise).
            white_username, white_elo = await _identity_for_role(ctx, room_id, Role.WHITE)
            black_username, black_elo = await _identity_for_role(ctx, room_id, Role.BLACK)
            return Envelope(type='state_sync', data={
                'role': reclaimed_role.value,
                'room_id': room_id,
                'state': state_sync_payload(room.engine),
                'white_username': white_username, 'white_elo': white_elo,
                'black_username': black_username, 'black_elo': black_elo,
            })
        # The room already ended before they reconnected (e.g. the other
        # player won in the meantime) — nothing to rebind into, fall
        # through to a normal login response.

    return Envelope(type='logged_in', data={'username': result.user.username, 'elo': result.user.elo})


async def _handle_queue_join(session: ClientSession, ctx: DispatchContext, _data: dict) -> Envelope:
    if session.user_id is None:
        return _error(ErrorCode.NOT_AUTHENTICATED)
    user = await ctx.users_repo.get_by_id(session.user_id)
    ctx.matchmaking_queue.enqueue(session.user_id, user.elo)
    # elo/range let the lobby show what band of opponents it's searching
    # (e.g. "ELO range 1100-1300") -- see lobby_window.py's _tick_countdown.
    return Envelope(type='queued', data={'elo': user.elo, 'range': ctx.matchmaking_queue.elo_range})


async def _handle_queue_cancel(session: ClientSession, ctx: DispatchContext, _data: dict) -> Envelope:
    if session.user_id is None:
        return _error(ErrorCode.NOT_AUTHENTICATED)
    was_queued = ctx.matchmaking_queue.dequeue(session.user_id)
    return Envelope(type='queue_cancelled', data={'was_queued': was_queued})


async def _handle_create_room(session: ClientSession, ctx: DispatchContext, _data: dict) -> Envelope:
    if session.user_id is None:
        return _error(ErrorCode.NOT_AUTHENTICATED)
    if session.room_id is not None:
        return _error(ErrorCode.ALREADY_IN_A_ROOM)

    user = await ctx.users_repo.get_by_id(session.user_id)
    room = ctx.room_manager.create_room()
    session.room_id, session.role = room.room_id, Role.WHITE
    ctx.room_membership.add(room.room_id, session.user_id, None)
    room.start()
    return Envelope(type='room_created', data={
        'room_id': room.room_id, 'role': Role.WHITE.value, 'state': state_sync_payload(room.engine),
        'white_username': user.username, 'white_elo': user.elo,
        'black_username': None, 'black_elo': None,
    })


async def _identity_for_role(ctx: DispatchContext, room_id: str, role: Role) -> Tuple[Optional[str], Optional[int]]:
    """(username, elo) of whoever currently holds `role` in room_id, or
    (None, None) if that seat isn't occupied yet -- used so a join_room
    reply can report both seats' identities, not just the joiner's own."""
    existing = next((s for s in ctx.session_manager.sessions if s.room_id == room_id and s.role is role), None)
    if existing is None or existing.user_id is None:
        return None, None
    user = await ctx.users_repo.get_by_id(existing.user_id)
    return (user.username, user.elo) if user is not None else (None, None)


async def _handle_join_room(session: ClientSession, ctx: DispatchContext, data: dict) -> Envelope:
    if session.user_id is None:
        return _error(ErrorCode.NOT_AUTHENTICATED)
    if session.room_id is not None:
        return _error(ErrorCode.ALREADY_IN_A_ROOM)

    room_id = data.get('room_id')
    if not isinstance(room_id, str) or not room_id:
        return _error(ErrorCode.MALFORMED_COMMAND)

    room = ctx.room_manager.get(room_id)
    if room is None:
        return _error(ErrorCode.ROOM_NOT_FOUND)

    role = _next_role_for(ctx.session_manager, room_id)
    white_username, white_elo = await _identity_for_role(ctx, room_id, Role.WHITE)
    black_username, black_elo = await _identity_for_role(ctx, room_id, Role.BLACK)

    joining_user = await ctx.users_repo.get_by_id(session.user_id)
    prev_white_id, prev_black_id = ctx.room_membership.get(room_id)
    if role is Role.WHITE:
        white_username, white_elo = joining_user.username, joining_user.elo
        ctx.room_membership.add(room_id, session.user_id, prev_black_id)
    elif role is Role.BLACK:
        black_username, black_elo = joining_user.username, joining_user.elo
        ctx.room_membership.add(room_id, prev_white_id, session.user_id)

    session.room_id, session.role = room_id, role
    return Envelope(type='room_joined', data={
        'room_id': room_id, 'role': role.value, 'state': state_sync_payload(room.engine),
        'white_username': white_username, 'white_elo': white_elo,
        'black_username': black_username, 'black_elo': black_elo,
    })


def _next_role_for(session_manager: SessionManager, room_id: str) -> Role:
    """1st joiner -> WHITE, 2nd -> BLACK, 3rd+ -> VIEWER."""
    occupied = {s.role for s in session_manager.sessions if s.room_id == room_id}
    if Role.WHITE not in occupied:
        return Role.WHITE
    if Role.BLACK not in occupied:
        return Role.BLACK
    return Role.VIEWER


_HANDLERS: Dict[str, Handler] = {
    'ping': _handle_ping,
    'move': _handle_move,
    'jump': _handle_jump,
    'check_username': _handle_check_username,
    'register': _handle_register,
    'login': _handle_login,
    'queue_join': _handle_queue_join,
    'queue_cancel': _handle_queue_cancel,
    'create_room': _handle_create_room,
    'join_room': _handle_join_room,
}


def build_dispatcher(
    room_manager: RoomManager, session_manager: SessionManager, users_repo: UsersRepository,
    matchmaking_queue: MatchmakingQueue, reconnect_state: ReconnectState,
    room_membership: Optional[RoomMembership] = None,
) -> Callable[[ClientSession, str], Awaitable[str]]:
    """
    Build the on_message callback network/server.py calls for every raw
    message a session sends. Always returns something to send back to the
    sender — malformed envelopes and unrecognized types get an error
    response of their own rather than being silently dropped.

    room_membership: pass main.py's own RoomMembership so create_room/
    join_room's writes land in the exact same object its on_game_over reads
    from -- omitted (tests that don't exercise a rated end-of-game) just
    gets a private one.
    """
    ctx = DispatchContext(room_manager, session_manager, users_repo, matchmaking_queue, reconnect_state,
                           room_membership=room_membership if room_membership is not None else RoomMembership())

    async def on_message(session: ClientSession, raw: str) -> str:
        try:
            envelope = decode(raw)
        except MalformedEnvelopeError:
            response = _error(ErrorCode.MALFORMED_COMMAND)
            log_command('recv', session.session_id, '<malformed>', {'raw': raw})
            log_command('sent', session.session_id, response.type, response.data)
            return encode(response)

        log_command('recv', session.session_id, envelope.type, envelope.data)

        handler = _HANDLERS.get(envelope.type)
        response = await handler(session, ctx, envelope.data) if handler is not None \
            else _error(ErrorCode.UNKNOWN_COMMAND)

        log_command('sent', session.session_id, response.type, response.data)
        return encode(response)

    return on_message
