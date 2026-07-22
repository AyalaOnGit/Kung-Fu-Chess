import json

import pytest

from core.bus import AsyncMessageBus
from core.clock import FakeClock
from core.protocol import decode
from db.connection import Database
from db.schema import init_schema
from db.users_repository import UsersRepository
from game.engine_factory import build_game_stack
from game.rooms import RoomManager
from matchmaking.queue import MatchmakingQueue
from network.dispatch import build_dispatcher
from network.server import SessionManager
from network.session import ClientSession, Role
from resilience.reconnect_state import ReconnectState

from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece, Color, Kind
from kungfu_chess.model.position import Position


def _minimal_board() -> Board:
    board = Board(width=8, height=8)
    board.add_piece(Piece(id=1, color=Color.WHITE, kind=Kind.KING, cell=Position(7, 7)))
    board.add_piece(Piece(id=2, color=Color.BLACK, kind=Kind.KING, cell=Position(7, 0)))
    board.add_piece(Piece(id=3, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0)))
    return board


async def _users_repo() -> UsersRepository:
    db = Database(':memory:')
    await db.run(init_schema)
    return UsersRepository(db)


def _queue() -> MatchmakingQueue:
    return MatchmakingQueue(clock=FakeClock())


def _reconnect_state() -> ReconnectState:
    return ReconnectState(clock=FakeClock())


class _Harness:
    """Bundles a RoomManager + SessionManager + dispatch() for one test."""

    def __init__(self, users_repo, queue=None, reconnect_state=None):
        self.session_manager = SessionManager()
        self.room_manager = RoomManager(AsyncMessageBus(), self.session_manager, log_events=False)
        self.queue = queue if queue is not None else _queue()
        self.reconnect_state = reconnect_state if reconnect_state is not None else _reconnect_state()
        self.dispatch = build_dispatcher(
            self.room_manager, self.session_manager, users_repo, self.queue, self.reconnect_state,
        )

    def new_session(self) -> ClientSession:
        """A session registered in session_manager, same as a real connection
        would be — join_room's role assignment scans session_manager.sessions,
        so tests exercising it need sessions to actually be tracked there."""
        return self.session_manager.admit(websocket=None)

    def room_with_a_rook(self):
        return self.room_manager.create_room(engine=build_game_stack(_minimal_board()))


async def _harness(queue=None, reconnect_state=None) -> _Harness:
    return _Harness(await _users_repo(), queue=queue, reconnect_state=reconnect_state)


async def _register(h: _Harness, session, username, password='hunter2'):
    return await h.dispatch(session, json.dumps({'type': 'register', 'data': {'username': username, 'password': password}}))


# --- ping / malformed / unknown ---

@pytest.mark.asyncio
async def test_ping_returns_pong():
    h = await _harness()
    session = h.new_session()

    raw = await h.dispatch(session, json.dumps({'type': 'ping', 'data': {}}))

    assert decode(raw).type == 'pong'


@pytest.mark.asyncio
async def test_malformed_json_returns_malformed_command_error():
    h = await _harness()
    session = h.new_session()

    raw = await h.dispatch(session, 'not json')

    envelope = decode(raw)
    assert envelope.type == 'error'
    assert envelope.data == {'code': 'malformed_command'}


@pytest.mark.asyncio
async def test_unrecognized_command_type_returns_unknown_command_error():
    h = await _harness()
    session = h.new_session()

    raw = await h.dispatch(session, json.dumps({'type': 'castle', 'data': {}}))

    envelope = decode(raw)
    assert envelope.type == 'error'
    assert envelope.data == {'code': 'unknown_command'}


# --- move/jump route through the session's room ---

@pytest.mark.asyncio
async def test_move_with_no_room_returns_not_in_a_match():
    h = await _harness()
    session = h.new_session()

    raw = await h.dispatch(session, json.dumps({'type': 'move', 'data': {'src': [0, 0], 'dest': [0, 3]}}))

    envelope = decode(raw)
    assert envelope.type == 'error'
    assert envelope.data == {'code': 'not_in_a_match'}


@pytest.mark.asyncio
async def test_accepted_move_returns_accepted():
    h = await _harness()
    room = h.room_with_a_rook()
    session = h.new_session()
    session.room_id, session.role = room.room_id, Role.WHITE

    raw = await h.dispatch(session, json.dumps({'type': 'move', 'data': {'src': [0, 0], 'dest': [0, 3]}}))

    assert decode(raw).type == 'accepted'
    await h.room_manager.end_room(room.room_id)


@pytest.mark.asyncio
async def test_rejected_move_returns_error_with_matching_code():
    h = await _harness()
    room = h.room_with_a_rook()
    session = h.new_session()
    session.room_id, session.role = room.room_id, Role.BLACK  # doesn't own (0, 0)

    raw = await h.dispatch(session, json.dumps({'type': 'move', 'data': {'src': [0, 0], 'dest': [0, 3]}}))

    envelope = decode(raw)
    assert envelope.type == 'error'
    assert envelope.data == {'code': 'not_your_piece'}
    await h.room_manager.end_room(room.room_id)


@pytest.mark.asyncio
async def test_accepted_jump_returns_accepted():
    h = await _harness()
    room = h.room_with_a_rook()
    session = h.new_session()
    session.room_id, session.role = room.room_id, Role.WHITE

    raw = await h.dispatch(session, json.dumps({'type': 'jump', 'data': {'cell': [0, 0]}}))

    assert decode(raw).type == 'accepted'
    await h.room_manager.end_room(room.room_id)


@pytest.mark.asyncio
async def test_move_referencing_an_ended_room_returns_not_in_a_match():
    h = await _harness()
    room = h.room_with_a_rook()
    session = h.new_session()
    session.room_id, session.role = room.room_id, Role.WHITE
    await h.room_manager.end_room(room.room_id)

    raw = await h.dispatch(session, json.dumps({'type': 'move', 'data': {'src': [0, 0], 'dest': [0, 3]}}))

    envelope = decode(raw)
    assert envelope.data == {'code': 'not_in_a_match'}


# --- check_username ---

@pytest.mark.asyncio
async def test_check_username_reports_false_for_an_unregistered_name():
    h = await _harness()
    session = h.new_session()

    raw = await h.dispatch(session, json.dumps({'type': 'check_username', 'data': {'username': 'nobody'}}))

    envelope = decode(raw)
    assert envelope.type == 'username_status'
    assert envelope.data == {'username': 'nobody', 'exists': False}


@pytest.mark.asyncio
async def test_check_username_reports_true_for_a_registered_name():
    h = await _harness()
    await _register(h, h.new_session(), 'alice')

    raw = await h.dispatch(h.new_session(), json.dumps({'type': 'check_username', 'data': {'username': 'alice'}}))

    envelope = decode(raw)
    assert envelope.data == {'username': 'alice', 'exists': True}


@pytest.mark.asyncio
async def test_check_username_rejects_a_missing_username():
    h = await _harness()
    session = h.new_session()

    raw = await h.dispatch(session, json.dumps({'type': 'check_username', 'data': {}}))

    assert decode(raw).data == {'code': 'malformed_command'}


# --- register/login ---

@pytest.mark.asyncio
async def test_register_succeeds_and_attaches_user_id_to_session():
    h = await _harness()
    session = h.new_session()

    raw = await _register(h, session, 'alice')

    envelope = decode(raw)
    assert envelope.type == 'registered'
    assert envelope.data == {'username': 'alice', 'elo': 1200}
    assert session.user_id is not None
    assert session.username == 'alice'


@pytest.mark.asyncio
async def test_register_malformed_payload_is_rejected():
    h = await _harness()
    session = h.new_session()

    raw = await h.dispatch(session, json.dumps({'type': 'register', 'data': {'username': 'alice'}}))

    envelope = decode(raw)
    assert envelope.data == {'code': 'malformed_command'}
    assert session.user_id is None


@pytest.mark.asyncio
async def test_register_duplicate_username_is_rejected():
    h = await _harness()
    await _register(h, h.new_session(), 'alice')
    session_b = h.new_session()

    raw = await _register(h, session_b, 'alice')

    envelope = decode(raw)
    assert envelope.data == {'code': 'username_taken'}
    assert session_b.user_id is None


@pytest.mark.asyncio
async def test_login_succeeds_and_attaches_user_id_to_session():
    h = await _harness()
    register_session = h.new_session()
    await _register(h, register_session, 'alice')

    login_session = h.new_session()
    raw = await h.dispatch(login_session, json.dumps({'type': 'login', 'data': {'username': 'alice', 'password': 'hunter2'}}))

    envelope = decode(raw)
    assert envelope.type == 'logged_in'
    assert login_session.user_id == register_session.user_id


@pytest.mark.asyncio
async def test_login_wrong_password_is_rejected():
    h = await _harness()
    await _register(h, h.new_session(), 'alice')

    login_session = h.new_session()
    raw = await h.dispatch(login_session, json.dumps({'type': 'login', 'data': {'username': 'alice', 'password': 'wrong'}}))

    envelope = decode(raw)
    assert envelope.data == {'code': 'invalid_credentials'}
    assert login_session.user_id is None


# --- reconnect via login ---

@pytest.mark.asyncio
async def test_login_with_no_pending_reconnect_returns_normal_logged_in():
    h = await _harness()
    await _register(h, h.new_session(), 'alice')

    login_session = h.new_session()
    raw = await h.dispatch(login_session, json.dumps({'type': 'login', 'data': {'username': 'alice', 'password': 'hunter2'}}))

    assert decode(raw).type == 'logged_in'
    assert login_session.role is None


@pytest.mark.asyncio
async def test_login_with_a_pending_reconnect_rebinds_role_and_room_and_returns_state_sync():
    h = await _harness()
    room = h.room_with_a_rook()
    original = h.new_session()
    await _register(h, original, 'alice')
    h.reconnect_state.mark_disconnected(original.user_id, Role.WHITE, room.room_id)

    new_socket_session = h.new_session()
    raw = await h.dispatch(new_socket_session, json.dumps({'type': 'login', 'data': {'username': 'alice', 'password': 'hunter2'}}))

    envelope = decode(raw)
    assert envelope.type == 'state_sync'
    assert envelope.data['role'] == 'white'
    assert envelope.data['room_id'] == room.room_id
    assert len(envelope.data['state']['pieces']) == 3  # _minimal_board()'s piece count
    assert new_socket_session.role is Role.WHITE
    assert new_socket_session.room_id == room.room_id
    assert new_socket_session.user_id not in h.reconnect_state  # one-shot

    await h.room_manager.end_room(room.room_id)


@pytest.mark.asyncio
async def test_login_reconnect_but_room_already_ended_falls_back_to_normal_login():
    h = await _harness()
    room = h.room_with_a_rook()
    session = h.new_session()
    await _register(h, session, 'alice')
    h.reconnect_state.mark_disconnected(session.user_id, Role.WHITE, room.room_id)
    await h.room_manager.end_room(room.room_id)

    new_socket_session = h.new_session()
    raw = await h.dispatch(new_socket_session, json.dumps({'type': 'login', 'data': {'username': 'alice', 'password': 'hunter2'}}))

    assert decode(raw).type == 'logged_in'
    assert new_socket_session.role is None


# --- queue_join/queue_cancel ---

@pytest.mark.asyncio
async def test_queue_join_requires_login():
    h = await _harness()
    session = h.new_session()

    raw = await h.dispatch(session, json.dumps({'type': 'queue_join', 'data': {}}))

    envelope = decode(raw)
    assert envelope.data == {'code': 'not_authenticated'}
    assert len(h.queue) == 0


@pytest.mark.asyncio
async def test_queue_join_enqueues_the_logged_in_user_at_their_current_elo():
    h = await _harness()
    session = h.new_session()
    await _register(h, session, 'alice')

    raw = await h.dispatch(session, json.dumps({'type': 'queue_join', 'data': {}}))

    envelope = decode(raw)
    assert envelope.type == 'queued'
    assert session.user_id in h.queue


@pytest.mark.asyncio
async def test_queue_cancel_removes_a_queued_user_and_reports_it():
    h = await _harness()
    session = h.new_session()
    await _register(h, session, 'alice')
    await h.dispatch(session, json.dumps({'type': 'queue_join', 'data': {}}))

    raw = await h.dispatch(session, json.dumps({'type': 'queue_cancel', 'data': {}}))

    envelope = decode(raw)
    assert envelope.data == {'was_queued': True}
    assert session.user_id not in h.queue


@pytest.mark.asyncio
async def test_queue_cancel_when_not_queued_reports_that_too():
    h = await _harness()
    session = h.new_session()
    await _register(h, session, 'alice')

    raw = await h.dispatch(session, json.dumps({'type': 'queue_cancel', 'data': {}}))

    assert decode(raw).data == {'was_queued': False}


# --- create_room/join_room ---

@pytest.mark.asyncio
async def test_create_room_requires_login():
    h = await _harness()
    session = h.new_session()

    raw = await h.dispatch(session, json.dumps({'type': 'create_room', 'data': {}}))

    assert decode(raw).data == {'code': 'not_authenticated'}


@pytest.mark.asyncio
async def test_create_room_makes_the_creator_white_and_starts_the_room():
    h = await _harness()
    session = h.new_session()
    await _register(h, session, 'alice')

    raw = await h.dispatch(session, json.dumps({'type': 'create_room', 'data': {}}))

    envelope = decode(raw)
    assert envelope.type == 'room_created'
    assert envelope.data['role'] == 'white'
    assert session.role is Role.WHITE
    assert session.room_id == envelope.data['room_id']
    assert h.room_manager.get(envelope.data['room_id']).is_running
    # A client (e.g. a viewer joining later, or the UI drawing the board on
    # entry) needs the starting position without a separate round-trip.
    assert len(envelope.data['state']['pieces']) == 32  # standard_board()

    await h.room_manager.end_room(envelope.data['room_id'])


@pytest.mark.asyncio
async def test_create_room_while_already_in_a_room_is_rejected():
    h = await _harness()
    session = h.new_session()
    await _register(h, session, 'alice')
    await h.dispatch(session, json.dumps({'type': 'create_room', 'data': {}}))

    raw = await h.dispatch(session, json.dumps({'type': 'create_room', 'data': {}}))

    assert decode(raw).data == {'code': 'already_in_a_room'}

    await h.room_manager.end_room(session.room_id)


@pytest.mark.asyncio
async def test_join_room_requires_login():
    h = await _harness()
    session = h.new_session()

    raw = await h.dispatch(session, json.dumps({'type': 'join_room', 'data': {'room_id': 'whatever'}}))

    assert decode(raw).data == {'code': 'not_authenticated'}


@pytest.mark.asyncio
async def test_join_room_with_unknown_room_id_is_rejected():
    h = await _harness()
    session = h.new_session()
    await _register(h, session, 'alice')

    raw = await h.dispatch(session, json.dumps({'type': 'join_room', 'data': {'room_id': 'nope'}}))

    assert decode(raw).data == {'code': 'room_not_found'}


@pytest.mark.asyncio
async def test_join_room_with_malformed_room_id_is_rejected():
    h = await _harness()
    session = h.new_session()
    await _register(h, session, 'alice')

    raw = await h.dispatch(session, json.dumps({'type': 'join_room', 'data': {}}))

    assert decode(raw).data == {'code': 'malformed_command'}


@pytest.mark.asyncio
async def test_join_room_role_progression_white_black_viewer():
    h = await _harness()

    creator = h.new_session()
    await _register(h, creator, 'alice')
    create_raw = await h.dispatch(creator, json.dumps({'type': 'create_room', 'data': {}}))
    room_id = decode(create_raw).data['room_id']

    second = h.new_session()
    await _register(h, second, 'bob')
    second_raw = await h.dispatch(second, json.dumps({'type': 'join_room', 'data': {'room_id': room_id}}))
    assert decode(second_raw).data['role'] == 'black'

    third = h.new_session()
    await _register(h, third, 'carol')
    third_raw = await h.dispatch(third, json.dumps({'type': 'join_room', 'data': {'room_id': room_id}}))
    assert decode(third_raw).data['role'] == 'viewer'

    await h.room_manager.end_room(room_id)


@pytest.mark.asyncio
async def test_join_room_returns_the_rooms_actual_current_state_not_a_fresh_board():
    """A late joiner (2nd player, or any viewer) must see the room's real
    position -- not an assumed standard starting layout -- since the room
    may already be mid-game by the time they join."""
    h = await _harness()
    room = h.room_with_a_rook()  # 3 pieces, not the standard 32

    joiner = h.new_session()
    await _register(h, joiner, 'bob')
    raw = await h.dispatch(joiner, json.dumps({'type': 'join_room', 'data': {'room_id': room.room_id}}))

    envelope = decode(raw)
    assert envelope.type == 'room_joined'
    assert len(envelope.data['state']['pieces']) == 3

    await h.room_manager.end_room(room.room_id)


@pytest.mark.asyncio
async def test_join_room_while_already_in_a_room_is_rejected():
    h = await _harness()
    creator = h.new_session()
    await _register(h, creator, 'alice')
    create_raw = await h.dispatch(creator, json.dumps({'type': 'create_room', 'data': {}}))
    room_id = decode(create_raw).data['room_id']

    raw = await h.dispatch(creator, json.dumps({'type': 'join_room', 'data': {'room_id': room_id}}))

    assert decode(raw).data == {'code': 'already_in_a_room'}

    await h.room_manager.end_room(room_id)
