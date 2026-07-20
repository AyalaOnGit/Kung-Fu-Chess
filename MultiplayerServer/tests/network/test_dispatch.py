import asyncio
import json

import pytest
from websockets.exceptions import ConnectionClosed

from core.bus import AsyncMessageBus
from core.clock import FakeClock
from core.protocol import decode
from db.connection import Database
from db.schema import init_schema
from db.users_repository import UsersRepository
from game.engine_factory import build_game_stack
from game.events import MoveAccepted
from game.match import TOPIC, MatchSession
from matchmaking.queue import MatchmakingQueue
from network.dispatch import build_broadcaster, build_dispatcher
from network.server import SessionManager
from network.session import ClientSession, Role

from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece, Color, Kind
from kungfu_chess.model.position import Position


def _minimal_board() -> Board:
    board = Board(width=8, height=8)
    board.add_piece(Piece(id=1, color=Color.WHITE, kind=Kind.KING, cell=Position(7, 7)))
    board.add_piece(Piece(id=2, color=Color.BLACK, kind=Kind.KING, cell=Position(7, 0)))
    board.add_piece(Piece(id=3, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0)))
    return board


def _match() -> MatchSession:
    return MatchSession(AsyncMessageBus(), engine=build_game_stack(_minimal_board()))


async def _users_repo() -> UsersRepository:
    db = Database(':memory:')
    await db.run(init_schema)
    return UsersRepository(db)


def _queue() -> MatchmakingQueue:
    return MatchmakingQueue(clock=FakeClock())


def _dispatch(match, users_repo, queue=None):
    return build_dispatcher(lambda: match, users_repo, queue if queue is not None else _queue())


# --- build_dispatcher: move/jump/ping ---

@pytest.mark.asyncio
async def test_ping_returns_pong():
    dispatch = _dispatch(_match(), await _users_repo())
    session = ClientSession.new(websocket=None, role=Role.WHITE)

    raw = await dispatch(session, json.dumps({'type': 'ping', 'data': {}}))

    assert decode(raw).type == 'pong'


@pytest.mark.asyncio
async def test_malformed_json_returns_malformed_command_error():
    dispatch = _dispatch(_match(), await _users_repo())
    session = ClientSession.new(websocket=None, role=Role.WHITE)

    raw = await dispatch(session, 'not json')

    envelope = decode(raw)
    assert envelope.type == 'error'
    assert envelope.data == {'code': 'malformed_command'}


@pytest.mark.asyncio
async def test_unrecognized_command_type_returns_unknown_command_error():
    dispatch = _dispatch(_match(), await _users_repo())
    session = ClientSession.new(websocket=None, role=Role.WHITE)

    raw = await dispatch(session, json.dumps({'type': 'castle', 'data': {}}))

    envelope = decode(raw)
    assert envelope.type == 'error'
    assert envelope.data == {'code': 'unknown_command'}


@pytest.mark.asyncio
async def test_accepted_move_returns_accepted():
    dispatch = _dispatch(_match(), await _users_repo())
    session = ClientSession.new(websocket=None, role=Role.WHITE)

    raw = await dispatch(session, json.dumps({'type': 'move', 'data': {'src': [0, 0], 'dest': [0, 3]}}))

    assert decode(raw).type == 'accepted'


@pytest.mark.asyncio
async def test_rejected_move_returns_error_with_matching_code():
    dispatch = _dispatch(_match(), await _users_repo())
    session = ClientSession.new(websocket=None, role=Role.BLACK)  # doesn't own (0, 0)

    raw = await dispatch(session, json.dumps({'type': 'move', 'data': {'src': [0, 0], 'dest': [0, 3]}}))

    envelope = decode(raw)
    assert envelope.type == 'error'
    assert envelope.data == {'code': 'not_your_piece'}


@pytest.mark.asyncio
async def test_accepted_jump_returns_accepted():
    dispatch = _dispatch(_match(), await _users_repo())
    session = ClientSession.new(websocket=None, role=Role.WHITE)

    raw = await dispatch(session, json.dumps({'type': 'jump', 'data': {'cell': [0, 0]}}))

    assert decode(raw).type == 'accepted'


@pytest.mark.asyncio
async def test_move_with_no_active_match_returns_not_in_a_match():
    dispatch = build_dispatcher(lambda: None, await _users_repo(), _queue())
    session = ClientSession.new(websocket=None, role=None)

    raw = await dispatch(session, json.dumps({'type': 'move', 'data': {'src': [0, 0], 'dest': [0, 3]}}))

    envelope = decode(raw)
    assert envelope.type == 'error'
    assert envelope.data == {'code': 'not_in_a_match'}


# --- build_dispatcher: register/login ---

@pytest.mark.asyncio
async def test_register_succeeds_and_attaches_user_id_to_session():
    dispatch = _dispatch(_match(), await _users_repo())
    session = ClientSession.new(websocket=None, role=Role.WHITE)

    raw = await dispatch(session, json.dumps({'type': 'register', 'data': {'username': 'alice', 'password': 'hunter2'}}))

    envelope = decode(raw)
    assert envelope.type == 'registered'
    assert envelope.data == {'username': 'alice', 'elo': 1200}
    assert session.user_id is not None
    assert session.username == 'alice'


@pytest.mark.asyncio
async def test_register_malformed_payload_is_rejected():
    dispatch = _dispatch(_match(), await _users_repo())
    session = ClientSession.new(websocket=None, role=Role.WHITE)

    raw = await dispatch(session, json.dumps({'type': 'register', 'data': {'username': 'alice'}}))

    envelope = decode(raw)
    assert envelope.type == 'error'
    assert envelope.data == {'code': 'malformed_command'}
    assert session.user_id is None


@pytest.mark.asyncio
async def test_register_duplicate_username_is_rejected():
    users_repo = await _users_repo()
    session_a = ClientSession.new(websocket=None, role=Role.WHITE)
    session_b = ClientSession.new(websocket=None, role=Role.BLACK)
    dispatch = _dispatch(_match(), users_repo)

    await dispatch(session_a, json.dumps({'type': 'register', 'data': {'username': 'alice', 'password': 'p1'}}))
    raw = await dispatch(session_b, json.dumps({'type': 'register', 'data': {'username': 'alice', 'password': 'p2'}}))

    envelope = decode(raw)
    assert envelope.type == 'error'
    assert envelope.data == {'code': 'username_taken'}
    assert session_b.user_id is None


@pytest.mark.asyncio
async def test_login_succeeds_and_attaches_user_id_to_session():
    users_repo = await _users_repo()
    register_session = ClientSession.new(websocket=None, role=Role.WHITE)
    dispatch = _dispatch(_match(), users_repo)
    await dispatch(register_session, json.dumps({'type': 'register', 'data': {'username': 'alice', 'password': 'hunter2'}}))

    login_session = ClientSession.new(websocket=None, role=Role.BLACK)
    raw = await dispatch(login_session, json.dumps({'type': 'login', 'data': {'username': 'alice', 'password': 'hunter2'}}))

    envelope = decode(raw)
    assert envelope.type == 'logged_in'
    assert login_session.user_id == register_session.user_id
    assert login_session.username == 'alice'


@pytest.mark.asyncio
async def test_login_wrong_password_is_rejected():
    users_repo = await _users_repo()
    dispatch = _dispatch(_match(), users_repo)
    reg_session = ClientSession.new(websocket=None, role=Role.WHITE)
    await dispatch(reg_session, json.dumps({'type': 'register', 'data': {'username': 'alice', 'password': 'hunter2'}}))

    login_session = ClientSession.new(websocket=None, role=Role.BLACK)
    raw = await dispatch(login_session, json.dumps({'type': 'login', 'data': {'username': 'alice', 'password': 'wrong'}}))

    envelope = decode(raw)
    assert envelope.type == 'error'
    assert envelope.data == {'code': 'invalid_credentials'}
    assert login_session.user_id is None


# --- build_dispatcher: queue_join/queue_cancel ---

@pytest.mark.asyncio
async def test_queue_join_requires_login():
    queue = _queue()
    dispatch = _dispatch(_match(), await _users_repo(), queue)
    session = ClientSession.new(websocket=None, role=None)  # never logged in

    raw = await dispatch(session, json.dumps({'type': 'queue_join', 'data': {}}))

    envelope = decode(raw)
    assert envelope.type == 'error'
    assert envelope.data == {'code': 'not_authenticated'}
    assert len(queue) == 0


@pytest.mark.asyncio
async def test_queue_join_enqueues_the_logged_in_user_at_their_current_elo():
    users_repo = await _users_repo()
    queue = _queue()
    dispatch = _dispatch(_match(), users_repo, queue)
    session = ClientSession.new(websocket=None, role=None)
    await dispatch(session, json.dumps({'type': 'register', 'data': {'username': 'alice', 'password': 'hunter2'}}))

    raw = await dispatch(session, json.dumps({'type': 'queue_join', 'data': {}}))

    envelope = decode(raw)
    assert envelope.type == 'queued'
    assert session.user_id in queue


@pytest.mark.asyncio
async def test_queue_cancel_requires_login():
    queue = _queue()
    dispatch = _dispatch(_match(), await _users_repo(), queue)
    session = ClientSession.new(websocket=None, role=None)

    raw = await dispatch(session, json.dumps({'type': 'queue_cancel', 'data': {}}))

    envelope = decode(raw)
    assert envelope.type == 'error'
    assert envelope.data == {'code': 'not_authenticated'}


@pytest.mark.asyncio
async def test_queue_cancel_removes_a_queued_user_and_reports_it():
    users_repo = await _users_repo()
    queue = _queue()
    dispatch = _dispatch(_match(), users_repo, queue)
    session = ClientSession.new(websocket=None, role=None)
    await dispatch(session, json.dumps({'type': 'register', 'data': {'username': 'alice', 'password': 'hunter2'}}))
    await dispatch(session, json.dumps({'type': 'queue_join', 'data': {}}))

    raw = await dispatch(session, json.dumps({'type': 'queue_cancel', 'data': {}}))

    envelope = decode(raw)
    assert envelope.type == 'queue_cancelled'
    assert envelope.data == {'was_queued': True}
    assert session.user_id not in queue


@pytest.mark.asyncio
async def test_queue_cancel_when_not_queued_reports_that_too():
    users_repo = await _users_repo()
    dispatch = _dispatch(_match(), users_repo)
    session = ClientSession.new(websocket=None, role=None)
    await dispatch(session, json.dumps({'type': 'register', 'data': {'username': 'alice', 'password': 'hunter2'}}))

    raw = await dispatch(session, json.dumps({'type': 'queue_cancel', 'data': {}}))

    envelope = decode(raw)
    assert envelope.data == {'was_queued': False}


# --- build_broadcaster ---

class _FakeWebSocket:
    def __init__(self, fail: bool = False):
        self.sent = []
        self._fail = fail

    async def send(self, raw: str) -> None:
        if self._fail:
            raise ConnectionClosed(None, None)
        self.sent.append(raw)


@pytest.mark.asyncio
async def test_broadcaster_forwards_event_to_the_two_match_participants():
    bus = AsyncMessageBus()
    session_manager = SessionManager()
    ws_white = _FakeWebSocket()
    ws_black = _FakeWebSocket()
    session_manager.admit(ws_white).role = Role.WHITE
    session_manager.admit(ws_black).role = Role.BLACK

    unsubscribe = build_broadcaster(bus, session_manager, TOPIC)
    try:
        piece = Piece(id=1, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 3))
        bus.publish(TOPIC, MoveAccepted(piece=piece, src=Position(0, 0), dest=Position(0, 3)))
        await asyncio.sleep(0.05)

        assert len(ws_white.sent) == 1
        assert len(ws_black.sent) == 1
        envelope = decode(ws_white.sent[0])
        assert envelope.type == 'move_accepted'
        assert envelope.data['src'] == [0, 0]
        assert envelope.data['dest'] == [0, 3]
    finally:
        unsubscribe()


@pytest.mark.asyncio
async def test_broadcaster_does_not_forward_to_bystanders_with_no_role():
    # Since Phase 3, more than two sessions can be connected at once (a
    # matchmaking queue) — anyone not currently in the active match
    # (role is None) must not see its broadcasts.
    bus = AsyncMessageBus()
    session_manager = SessionManager()
    ws_white = _FakeWebSocket()
    ws_black = _FakeWebSocket()
    ws_bystander = _FakeWebSocket()
    session_manager.admit(ws_white).role = Role.WHITE
    session_manager.admit(ws_black).role = Role.BLACK
    session_manager.admit(ws_bystander)  # still queued, role stays None

    unsubscribe = build_broadcaster(bus, session_manager, TOPIC)
    try:
        piece = Piece(id=1, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 3))
        bus.publish(TOPIC, MoveAccepted(piece=piece, src=Position(0, 0), dest=Position(0, 3)))
        await asyncio.sleep(0.05)

        assert len(ws_white.sent) == 1
        assert len(ws_black.sent) == 1
        assert ws_bystander.sent == []
    finally:
        unsubscribe()


@pytest.mark.asyncio
async def test_broadcaster_skips_a_session_whose_send_fails_without_crashing():
    bus = AsyncMessageBus()
    session_manager = SessionManager()
    ws_gone = _FakeWebSocket(fail=True)
    ws_ok = _FakeWebSocket()
    session_manager.admit(ws_gone).role = Role.WHITE
    session_manager.admit(ws_ok).role = Role.BLACK

    unsubscribe = build_broadcaster(bus, session_manager, TOPIC)
    try:
        piece = Piece(id=1, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 3))
        bus.publish(TOPIC, MoveAccepted(piece=piece, src=Position(0, 0), dest=Position(0, 3)))
        await asyncio.sleep(0.05)

        assert ws_gone.sent == []
        assert len(ws_ok.sent) == 1
    finally:
        unsubscribe()


@pytest.mark.asyncio
async def test_unsubscribed_broadcaster_stops_delivery():
    bus = AsyncMessageBus()
    session_manager = SessionManager()
    ws = _FakeWebSocket()
    session_manager.admit(ws).role = Role.WHITE

    unsubscribe = build_broadcaster(bus, session_manager, TOPIC)
    unsubscribe()

    piece = Piece(id=1, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 3))
    bus.publish(TOPIC, MoveAccepted(piece=piece, src=Position(0, 0), dest=Position(0, 3)))
    await asyncio.sleep(0.05)

    assert ws.sent == []
