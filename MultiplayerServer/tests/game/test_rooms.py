import asyncio
from unittest.mock import patch

import pytest

from core.bus import AsyncMessageBus
from game.engine_factory import build_game_stack
from game.events import GameOver, PieceArrived
from game.rooms import Room, RoomManager, topic_for
from network.server import SessionManager
from network.session import ClientSession
from core.protocol import Role

from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece, Color, Kind
from kungfu_chess.model.position import Position


def _minimal_board() -> Board:
    board = Board(width=8, height=8)
    board.add_piece(Piece(id=1, color=Color.WHITE, kind=Kind.KING, cell=Position(7, 7)))
    board.add_piece(Piece(id=2, color=Color.BLACK, kind=Kind.KING, cell=Position(7, 0)))
    board.add_piece(Piece(id=3, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0)))
    return board


def _king_capture_board() -> Board:
    board = Board(width=8, height=8)
    board.add_piece(Piece(id=1, color=Color.WHITE, kind=Kind.KING, cell=Position(7, 7)))
    board.add_piece(Piece(id=2, color=Color.BLACK, kind=Kind.KING, cell=Position(0, 3)))
    board.add_piece(Piece(id=3, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0)))
    return board


# --- Room lifecycle ---

def test_default_construction_uses_the_standard_starting_board():
    room = Room('r1', AsyncMessageBus())
    assert len(room.engine.board.all_pieces()) == 32
    assert not room.is_running


def test_explicit_engine_is_used_as_is():
    engine = build_game_stack(_minimal_board())
    room = Room('r1', AsyncMessageBus(), engine=engine)
    assert room.engine is engine


def test_topic_is_derived_from_room_id():
    room = Room('abcd', AsyncMessageBus())
    assert room.topic == topic_for('abcd') == 'room:abcd'


@pytest.mark.asyncio
async def test_start_stop_lifecycle_matches_match_session():
    room = Room('r1', AsyncMessageBus(), engine=build_game_stack(_minimal_board()), tick_interval_ms=20)
    room.start()
    try:
        assert room.is_running
        with pytest.raises(RuntimeError):
            room.start()
    finally:
        await room.stop()
    assert not room.is_running
    await room.stop()  # idempotent


@pytest.mark.asyncio
async def test_stop_leaves_no_lingering_task():
    room = Room('r1', AsyncMessageBus(), engine=build_game_stack(_minimal_board()), tick_interval_ms=20)
    tasks_before = asyncio.all_tasks()
    room.start()
    await asyncio.sleep(0.03)
    assert asyncio.all_tasks() - tasks_before

    await room.stop()
    await asyncio.sleep(0)
    assert asyncio.all_tasks() - tasks_before == set()


def test_handle_move_delegates_to_commands_and_engine():
    room = Room('r1', AsyncMessageBus(), engine=build_game_stack(_minimal_board()))
    session = ClientSession.new(websocket=None, role=Role.WHITE)

    result = room.handle_move(session, {'src': [0, 0], 'dest': [0, 3]})

    assert result.accepted


def test_handle_jump_delegates_to_commands_and_engine():
    room = Room('r1', AsyncMessageBus(), engine=build_game_stack(_minimal_board()))
    session = ClientSession.new(websocket=None, role=Role.WHITE)

    result = room.handle_jump(session, {'cell': [0, 0]})

    assert result.accepted


@pytest.mark.asyncio
async def test_on_game_over_fires_with_room_id_winner_loser_reason_on_capture():
    calls = []

    async def on_game_over(room_id, winner_role, loser_role, reason):
        calls.append((room_id, winner_role, loser_role, reason))

    room = Room('capture-room', AsyncMessageBus(), engine=build_game_stack(_king_capture_board()),
                tick_interval_ms=20, on_game_over=on_game_over)
    session = ClientSession.new(websocket=None, role=Role.WHITE)

    try:
        room.start()
        result = room.handle_move(session, {'src': [0, 0], 'dest': [0, 3]})
        assert result.accepted

        for _ in range(100):
            if calls:
                break
            await asyncio.sleep(0.05)
    finally:
        await room.stop()

    assert calls == [('capture-room', Role.WHITE, Role.BLACK, 'king_captured')]


@pytest.mark.asyncio
async def test_resign_sets_game_over_and_calls_on_game_over_with_room_id_and_reason():
    calls = []

    async def on_game_over(room_id, winner_role, loser_role, reason):
        calls.append((room_id, winner_role, loser_role, reason))

    room = Room('r1', AsyncMessageBus(), engine=build_game_stack(_minimal_board()), on_game_over=on_game_over)

    await room.resign(Role.WHITE, 'disconnect_timeout')

    assert room.engine.game_over
    assert calls == [('r1', Role.BLACK, Role.WHITE, 'disconnect_timeout')]


@pytest.mark.asyncio
async def test_resign_publishes_a_game_over_event_on_the_rooms_own_topic():
    bus = AsyncMessageBus()
    room = Room('r1', bus, engine=build_game_stack(_minimal_board()))

    received = []
    got_it = asyncio.Event()

    async def handler(event):
        received.append(event)
        got_it.set()

    unsubscribe = bus.subscribe(topic_for('r1'), handler)
    try:
        await room.resign(Role.BLACK, 'disconnect_timeout')
        await asyncio.wait_for(got_it.wait(), timeout=1.0)

        assert isinstance(received[0], GameOver)
        assert received[0].winner is Color.WHITE
        assert received[0].loser is Color.BLACK
    finally:
        unsubscribe()


@pytest.mark.asyncio
async def test_resign_is_idempotent():
    calls = []

    async def on_game_over(room_id, winner_role, loser_role, reason):
        calls.append(1)

    room = Room('r1', AsyncMessageBus(), engine=build_game_stack(_minimal_board()), on_game_over=on_game_over)

    await room.resign(Role.WHITE, 'disconnect_timeout')
    await room.resign(Role.WHITE, 'disconnect_timeout')

    assert len(calls) == 1


# --- RoomManager: id generation ---

@pytest.mark.asyncio
async def test_create_room_generates_a_room_id_and_registers_it():
    session_manager = SessionManager()
    manager = RoomManager(AsyncMessageBus(), session_manager, log_events=False)

    room = manager.create_room()
    try:
        assert room.room_id
        assert manager.get(room.room_id) is room
    finally:
        await manager.end_room(room.room_id)


@pytest.mark.asyncio
async def test_create_room_twice_yields_distinct_room_ids():
    session_manager = SessionManager()
    manager = RoomManager(AsyncMessageBus(), session_manager, log_events=False)

    room_a = manager.create_room()
    room_b = manager.create_room()
    try:
        assert room_a.room_id != room_b.room_id
        assert len(manager.rooms) == 2
    finally:
        await manager.end_room(room_a.room_id)
        await manager.end_room(room_b.room_id)


@pytest.mark.asyncio
async def test_create_room_retries_on_id_collision():
    session_manager = SessionManager()
    manager = RoomManager(AsyncMessageBus(), session_manager, log_events=False)
    manager._rooms['dup'] = Room('dup', AsyncMessageBus())  # pre-occupy 'dup'

    with patch('game.rooms.secrets.token_urlsafe', side_effect=['dup', 'unique']):
        room = manager.create_room()

    try:
        assert room.room_id == 'unique'
    finally:
        await manager.end_room(room.room_id)


def test_create_room_gives_up_after_repeated_collisions():
    session_manager = SessionManager()
    manager = RoomManager(AsyncMessageBus(), session_manager, log_events=False)
    manager._rooms['dup'] = Room('dup', AsyncMessageBus())

    with patch('game.rooms.secrets.token_urlsafe', return_value='dup'):
        with pytest.raises(RuntimeError):
            manager.create_room()


def test_get_returns_none_for_unknown_room_id():
    manager = RoomManager(AsyncMessageBus(), SessionManager(), log_events=False)
    assert manager.get('nope') is None


# --- RoomManager: teardown ---

@pytest.mark.asyncio
async def test_end_room_stops_and_removes_the_room():
    session_manager = SessionManager()
    manager = RoomManager(AsyncMessageBus(), session_manager, log_events=False)
    room = manager.create_room(engine=build_game_stack(_minimal_board()))
    room.start()

    await manager.end_room(room.room_id)

    assert manager.get(room.room_id) is None
    assert not room.is_running


@pytest.mark.asyncio
async def test_end_room_is_idempotent():
    manager = RoomManager(AsyncMessageBus(), SessionManager(), log_events=False)
    room = manager.create_room(engine=build_game_stack(_minimal_board()))

    await manager.end_room(room.room_id)
    await manager.end_room(room.room_id)  # must not raise
    await manager.end_room('never-existed')  # must not raise


@pytest.mark.asyncio
async def test_end_room_unsubscribes_the_broadcaster():
    bus = AsyncMessageBus()
    session_manager = SessionManager()
    manager = RoomManager(bus, session_manager, log_events=False)
    room = manager.create_room(engine=build_game_stack(_minimal_board()))

    class _FakeWebSocket:
        def __init__(self):
            self.sent = []

        async def send(self, raw):
            self.sent.append(raw)

    ws = _FakeWebSocket()
    session = session_manager.admit(ws)
    session.role, session.room_id = Role.WHITE, room.room_id

    await manager.end_room(room.room_id)

    piece = Piece(id=99, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0))
    bus.publish(room.topic, PieceArrived(piece=piece, pos=Position(0, 0)))
    await asyncio.sleep(0.05)

    assert ws.sent == []  # no lingering subscription


# --- RoomManager: broadcaster scoping (concurrency + viewers) ---

class _FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send(self, raw: str) -> None:
        self.sent.append(raw)


@pytest.mark.asyncio
async def test_broadcaster_reaches_players_and_viewers_in_the_same_room():
    bus = AsyncMessageBus()
    session_manager = SessionManager()
    manager = RoomManager(bus, session_manager, log_events=False)
    room = manager.create_room(engine=build_game_stack(_minimal_board()))

    white_ws, black_ws, viewer_ws = _FakeWebSocket(), _FakeWebSocket(), _FakeWebSocket()
    white = session_manager.admit(white_ws)
    black = session_manager.admit(black_ws)
    viewer = session_manager.admit(viewer_ws)
    white.role, white.room_id = Role.WHITE, room.room_id
    black.role, black.room_id = Role.BLACK, room.room_id
    viewer.role, viewer.room_id = Role.VIEWER, room.room_id

    try:
        piece = Piece(id=1, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0))
        bus.publish(room.topic, PieceArrived(piece=piece, pos=Position(0, 0)))
        await asyncio.sleep(0.05)

        assert len(white_ws.sent) == 1
        assert len(black_ws.sent) == 1
        assert len(viewer_ws.sent) == 1
    finally:
        await manager.end_room(room.room_id)


@pytest.mark.asyncio
async def test_two_concurrent_rooms_do_not_leak_events_to_each_other():
    bus = AsyncMessageBus()
    session_manager = SessionManager()
    manager = RoomManager(bus, session_manager, log_events=False)
    room_a = manager.create_room(engine=build_game_stack(_minimal_board()))
    room_b = manager.create_room(engine=build_game_stack(_minimal_board()))

    ws_a, ws_b = _FakeWebSocket(), _FakeWebSocket()
    session_a = session_manager.admit(ws_a)
    session_b = session_manager.admit(ws_b)
    session_a.role, session_a.room_id = Role.WHITE, room_a.room_id
    session_b.role, session_b.room_id = Role.WHITE, room_b.room_id

    try:
        piece = Piece(id=1, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0))
        bus.publish(room_a.topic, PieceArrived(piece=piece, pos=Position(0, 0)))
        await asyncio.sleep(0.05)

        assert len(ws_a.sent) == 1
        assert ws_b.sent == []  # room_b's session never saw room_a's event
    finally:
        await manager.end_room(room_a.room_id)
        await manager.end_room(room_b.room_id)


@pytest.mark.asyncio
async def test_bystander_with_no_room_does_not_receive_broadcasts():
    bus = AsyncMessageBus()
    session_manager = SessionManager()
    manager = RoomManager(bus, session_manager, log_events=False)
    room = manager.create_room(engine=build_game_stack(_minimal_board()))

    ws_player, ws_bystander = _FakeWebSocket(), _FakeWebSocket()
    player = session_manager.admit(ws_player)
    player.role, player.room_id = Role.WHITE, room.room_id
    session_manager.admit(ws_bystander)  # never joined any room

    try:
        piece = Piece(id=1, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0))
        bus.publish(room.topic, PieceArrived(piece=piece, pos=Position(0, 0)))
        await asyncio.sleep(0.05)

        assert len(ws_player.sent) == 1
        assert ws_bystander.sent == []
    finally:
        await manager.end_room(room.room_id)
