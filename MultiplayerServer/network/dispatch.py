"""
Command Pattern: envelope['type'] -> registered async handler. Adding a
wire command means registering one function in _HANDLERS, never editing a
branch chain.

Three responsibilities live here, all at the network/game seam:
  - build_dispatcher: routes an incoming raw message to game/commands.py
    (via the currently active MatchSession, if any) or auth/service.py
    (via UsersRepository) or matchmaking/queue.py, and returns the direct
    response for the sender alone.
  - build_broadcaster: subscribes to the match's Bus topic and fans every
    accepted game event out to all connected sessions.

The active match changes over a process's lifetime (Phase 3 on: created
per pairing, torn down at game-over) — get_current_match is a callable
rather than a fixed MatchSession so the dispatcher always sees the live
one instead of a stale reference captured once at startup.

Neither function imports kungfu_chess directly — game/wire.py (§1: "the
only package that imports kungfu_chess is game/") does the translation
from game events to JSON-safe dicts, so this module only ever handles
plain str/dict/Envelope values.
"""
from __future__ import annotations
import logging
from typing import Awaitable, Callable, Dict, Optional

from websockets.exceptions import ConnectionClosed

from auth import service as auth_service
from core.bus import AsyncMessageBus, Unsubscribe
from core.protocol import ErrorCode, Envelope, MalformedEnvelopeError, decode, encode
from db.users_repository import UsersRepository
from game.commands import HandleResult
from game.match import MatchSession
from game.wire import to_wire
from matchmaking.queue import MatchmakingQueue
from network.session import ClientSession
from network.server import SessionManager

logger = logging.getLogger(__name__)

GetCurrentMatch = Callable[[], Optional[MatchSession]]
Handler = Callable[[ClientSession, GetCurrentMatch, UsersRepository, MatchmakingQueue, dict], Awaitable[Envelope]]


def _result_envelope(result: HandleResult) -> Envelope:
    if result.accepted:
        return Envelope(type='accepted', data={})
    return Envelope(type='error', data={'code': result.error.value})


def _error(code: ErrorCode) -> Envelope:
    return Envelope(type='error', data={'code': code.value})


async def _handle_ping(_session: ClientSession, _get_match: GetCurrentMatch,
                        _users_repo: UsersRepository, _queue: MatchmakingQueue, _data: dict) -> Envelope:
    return Envelope(type='pong', data={})


async def _handle_move(session: ClientSession, get_match: GetCurrentMatch,
                        _users_repo: UsersRepository, _queue: MatchmakingQueue, data: dict) -> Envelope:
    match = get_match()
    if match is None:
        return _error(ErrorCode.NOT_IN_A_MATCH)
    return _result_envelope(match.handle_move(session, data))


async def _handle_jump(session: ClientSession, get_match: GetCurrentMatch,
                        _users_repo: UsersRepository, _queue: MatchmakingQueue, data: dict) -> Envelope:
    match = get_match()
    if match is None:
        return _error(ErrorCode.NOT_IN_A_MATCH)
    return _result_envelope(match.handle_jump(session, data))


def _credentials(data: dict):
    """Return (username, password) if both are non-empty strings, else None."""
    username, password = data.get('username'), data.get('password')
    if not isinstance(username, str) or not username or not isinstance(password, str) or not password:
        return None
    return username, password


async def _handle_register(session: ClientSession, _get_match: GetCurrentMatch,
                            users_repo: UsersRepository, _queue: MatchmakingQueue, data: dict) -> Envelope:
    credentials = _credentials(data)
    if credentials is None:
        return _error(ErrorCode.MALFORMED_COMMAND)

    result = await auth_service.register(users_repo, *credentials)
    if not result.ok:
        return _error(ErrorCode(result.error))

    session.user_id, session.username = result.user.id, result.user.username
    return Envelope(type='registered', data={'username': result.user.username, 'elo': result.user.elo})


async def _handle_login(session: ClientSession, _get_match: GetCurrentMatch,
                         users_repo: UsersRepository, _queue: MatchmakingQueue, data: dict) -> Envelope:
    credentials = _credentials(data)
    if credentials is None:
        return _error(ErrorCode.MALFORMED_COMMAND)

    result = await auth_service.login(users_repo, *credentials)
    if not result.ok:
        return _error(ErrorCode(result.error))

    session.user_id, session.username = result.user.id, result.user.username
    return Envelope(type='logged_in', data={'username': result.user.username, 'elo': result.user.elo})


async def _handle_queue_join(session: ClientSession, _get_match: GetCurrentMatch,
                              users_repo: UsersRepository, queue: MatchmakingQueue, _data: dict) -> Envelope:
    if session.user_id is None:
        return _error(ErrorCode.NOT_AUTHENTICATED)
    user = await users_repo.get_by_id(session.user_id)
    queue.enqueue(session.user_id, user.elo)
    return Envelope(type='queued', data={})


async def _handle_queue_cancel(session: ClientSession, _get_match: GetCurrentMatch,
                                _users_repo: UsersRepository, queue: MatchmakingQueue, _data: dict) -> Envelope:
    if session.user_id is None:
        return _error(ErrorCode.NOT_AUTHENTICATED)
    was_queued = queue.dequeue(session.user_id)
    return Envelope(type='queue_cancelled', data={'was_queued': was_queued})


_HANDLERS: Dict[str, Handler] = {
    'ping': _handle_ping,
    'move': _handle_move,
    'jump': _handle_jump,
    'register': _handle_register,
    'login': _handle_login,
    'queue_join': _handle_queue_join,
    'queue_cancel': _handle_queue_cancel,
}


def build_dispatcher(
    get_current_match: GetCurrentMatch, users_repo: UsersRepository, matchmaking_queue: MatchmakingQueue,
) -> Callable[[ClientSession, str], Awaitable[str]]:
    """
    Build the on_message callback network/server.py calls for every raw
    message a session sends. Always returns something to send back to the
    sender — malformed envelopes and unrecognized types get an error
    response of their own rather than being silently dropped.
    """

    async def on_message(session: ClientSession, raw: str) -> str:
        try:
            envelope = decode(raw)
        except MalformedEnvelopeError:
            return encode(_error(ErrorCode.MALFORMED_COMMAND))

        handler = _HANDLERS.get(envelope.type)
        if handler is None:
            return encode(_error(ErrorCode.UNKNOWN_COMMAND))

        return encode(await handler(session, get_current_match, users_repo, matchmaking_queue, envelope.data))

    return on_message


def build_broadcaster(bus: AsyncMessageBus, session_manager: SessionManager, topic: str) -> Unsubscribe:
    """
    Subscribe to topic and fan every game event out to the two active match
    participants — sessions with role is not None. Since Phase 3, session
    count can exceed two (a matchmaking queue of bystanders waiting their
    turn), and those bystanders must not see a match they aren't part of;
    role doubles as "is this session in the currently active match" for
    exactly that reason.
    """

    async def handler(event) -> None:
        envelope_type, data = to_wire(event)
        raw = encode(Envelope(type=envelope_type, data=data))
        for session in session_manager.sessions:
            if session.role is None:
                continue
            try:
                await session.websocket.send(raw)
            except ConnectionClosed:
                pass  # the session's own connection handler will clean it up

    return bus.subscribe(topic, handler)
