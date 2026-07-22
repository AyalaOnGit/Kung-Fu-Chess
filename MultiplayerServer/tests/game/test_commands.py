import asyncio
import types

import pytest

from core.bus import AsyncMessageBus
from core.protocol import ErrorCode, Role
from game.commands import HandleResult, handle_jump, handle_move
from game.engine_factory import build_game_stack
from game.events import JumpAccepted, MoveAccepted
from network.session import ClientSession

from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece, Color, Kind
from kungfu_chess.model.position import Position


def _session(role: Role) -> ClientSession:
    return ClientSession.new(websocket=None, role=role)


def _board() -> Board:
    board = Board(width=8, height=8)
    board.add_piece(Piece(id=1, color=Color.WHITE, kind=Kind.KING, cell=Position(7, 7)))
    board.add_piece(Piece(id=2, color=Color.BLACK, kind=Kind.KING, cell=Position(7, 0)))
    board.add_piece(Piece(id=3, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0)))
    board.add_piece(Piece(id=4, color=Color.BLACK, kind=Kind.ROOK, cell=Position(3, 3)))
    return board


async def _publish_and_capture(bus: AsyncMessageBus, topic: str):
    """Subscribe to topic, return (received_list, unsubscribe)."""
    received = []
    got_it = asyncio.Event()

    async def handler(event):
        received.append(event)
        got_it.set()

    unsubscribe = bus.subscribe(topic, handler)
    return received, got_it, unsubscribe


# --- Viewer short-circuit ---

@pytest.mark.asyncio
async def test_viewer_role_is_rejected_before_touching_the_engine():
    # A role that cannot move, stubbed with a duck-typed object rather than
    # a real Role member — VIEWER doesn't exist as a Role value until
    # Phase 5. engine=None proves the engine is never touched: if the
    # short-circuit didn't fire first, this would raise AttributeError.
    fake_session = types.SimpleNamespace(role=types.SimpleNamespace(can_move=False, value='viewer'))
    bus = AsyncMessageBus()

    result = handle_move(fake_session, None, bus, 'room:test', {'src': [0, 0], 'dest': [0, 1]})

    assert result == HandleResult(accepted=False, error=ErrorCode.VIEWER_READ_ONLY)


@pytest.mark.asyncio
async def test_unmatched_session_is_rejected_before_touching_the_engine():
    # A real ClientSession that was admitted but never paired into a match
    # (Phase 3 on) has role=None. engine=None again proves the engine is
    # never touched.
    session = ClientSession.new(websocket=None, role=None)
    bus = AsyncMessageBus()

    result = handle_move(session, None, bus, 'room:test', {'src': [0, 0], 'dest': [0, 1]})

    assert result == HandleResult(accepted=False, error=ErrorCode.NOT_IN_A_MATCH)


# --- Parsing ---

@pytest.mark.parametrize('data', [
    {},
    {'src': [0, 0]},
    {'src': None, 'dest': [0, 1]},
    {'src': [0], 'dest': [0, 1]},
    {'src': [0, 0, 0], 'dest': [0, 1]},
    {'src': ['a', 0], 'dest': [0, 1]},
    {'src': [True, 0], 'dest': [0, 1]},
    {'src': 'e2', 'dest': [0, 1]},
])
@pytest.mark.asyncio
async def test_malformed_move_payload_is_rejected(data):
    engine = build_game_stack(_board())
    bus = AsyncMessageBus()
    session = _session(Role.WHITE)

    result = handle_move(session, engine, bus, 'room:test', data)

    assert result == HandleResult(accepted=False, error=ErrorCode.MALFORMED_COMMAND)


# --- Ownership (the actual anti-cheat gate) ---

@pytest.mark.asyncio
async def test_empty_source_is_rejected():
    engine = build_game_stack(_board())
    bus = AsyncMessageBus()
    session = _session(Role.WHITE)

    result = handle_move(session, engine, bus, 'room:test', {'src': [5, 5], 'dest': [5, 6]})

    assert result == HandleResult(accepted=False, error=ErrorCode.EMPTY_SOURCE)


@pytest.mark.asyncio
async def test_white_session_cannot_move_a_black_piece():
    engine = build_game_stack(_board())
    bus = AsyncMessageBus()
    session = _session(Role.WHITE)

    # (3, 3) holds the black rook; a white session has no claim on it,
    # regardless of what the message asks for.
    result = handle_move(session, engine, bus, 'room:test', {'src': [3, 3], 'dest': [3, 5]})

    assert result == HandleResult(accepted=False, error=ErrorCode.NOT_YOUR_PIECE)


@pytest.mark.asyncio
async def test_black_session_cannot_move_a_white_piece():
    engine = build_game_stack(_board())
    bus = AsyncMessageBus()
    session = _session(Role.BLACK)

    result = handle_move(session, engine, bus, 'room:test', {'src': [0, 0], 'dest': [0, 3]})

    assert result == HandleResult(accepted=False, error=ErrorCode.NOT_YOUR_PIECE)


# --- Optional piece-kind integrity check ---

@pytest.mark.asyncio
async def test_wrong_claimed_piece_kind_is_rejected():
    engine = build_game_stack(_board())
    bus = AsyncMessageBus()
    session = _session(Role.WHITE)

    result = handle_move(session, engine, bus, 'room:test',
                          {'src': [0, 0], 'dest': [0, 3], 'piece_kind': 'Q'})

    assert result == HandleResult(accepted=False, error=ErrorCode.PIECE_MISMATCH)


@pytest.mark.asyncio
async def test_omitted_piece_kind_is_not_required():
    engine = build_game_stack(_board())
    bus = AsyncMessageBus()
    session = _session(Role.WHITE)

    result = handle_move(session, engine, bus, 'room:test', {'src': [0, 0], 'dest': [0, 3]})

    assert result.accepted


# --- Engine-level rejections translate to matching ErrorCodes ---

@pytest.mark.asyncio
async def test_illegal_destination_is_translated_to_illegal_move():
    engine = build_game_stack(_board())
    bus = AsyncMessageBus()
    session = _session(Role.WHITE)

    # A rook cannot move diagonally.
    result = handle_move(session, engine, bus, 'room:test', {'src': [0, 0], 'dest': [1, 1]})

    assert result == HandleResult(accepted=False, error=ErrorCode.ILLEGAL_MOVE)


@pytest.mark.asyncio
async def test_friendly_destination_is_translated_to_friendly_dest():
    board = _board()
    board.add_piece(Piece(id=5, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 3)))
    engine = build_game_stack(board)
    bus = AsyncMessageBus()
    session = _session(Role.WHITE)

    result = handle_move(session, engine, bus, 'room:test', {'src': [0, 0], 'dest': [0, 3]})

    assert result == HandleResult(accepted=False, error=ErrorCode.FRIENDLY_DEST)


# --- Happy path publishes to the bus ---

@pytest.mark.asyncio
async def test_accepted_move_publishes_move_accepted():
    engine = build_game_stack(_board())
    bus = AsyncMessageBus()
    session = _session(Role.WHITE)
    received, got_it, unsubscribe = await _publish_and_capture(bus, 'room:test')

    try:
        result = handle_move(session, engine, bus, 'room:test', {'src': [0, 0], 'dest': [0, 3]})
        assert result == HandleResult(accepted=True)

        await asyncio.wait_for(got_it.wait(), timeout=1.0)
        assert len(received) == 1
        assert isinstance(received[0], MoveAccepted)
        assert received[0].piece.kind is Kind.ROOK
        assert received[0].src == Position(0, 0)
        assert received[0].dest == Position(0, 3)
    finally:
        unsubscribe()


@pytest.mark.asyncio
async def test_rejected_move_publishes_nothing():
    engine = build_game_stack(_board())
    bus = AsyncMessageBus()
    session = _session(Role.WHITE)
    received, _got_it, unsubscribe = await _publish_and_capture(bus, 'room:test')

    try:
        result = handle_move(session, engine, bus, 'room:test', {'src': [0, 0], 'dest': [1, 1]})
        assert not result.accepted

        await asyncio.sleep(0.05)
        assert received == []
    finally:
        unsubscribe()


# --- handle_jump mirrors the same pipeline ---

@pytest.mark.asyncio
async def test_jump_rejects_someone_elses_piece():
    engine = build_game_stack(_board())
    bus = AsyncMessageBus()
    session = _session(Role.WHITE)

    result = handle_jump(session, engine, bus, 'room:test', {'cell': [3, 3]})

    assert result == HandleResult(accepted=False, error=ErrorCode.NOT_YOUR_PIECE)


@pytest.mark.asyncio
async def test_accepted_jump_publishes_jump_accepted():
    engine = build_game_stack(_board())
    bus = AsyncMessageBus()
    session = _session(Role.WHITE)
    received, got_it, unsubscribe = await _publish_and_capture(bus, 'room:test')

    try:
        result = handle_jump(session, engine, bus, 'room:test', {'cell': [0, 0]})
        assert result == HandleResult(accepted=True)

        await asyncio.wait_for(got_it.wait(), timeout=1.0)
        assert len(received) == 1
        assert isinstance(received[0], JumpAccepted)
        assert received[0].piece.kind is Kind.ROOK
        assert received[0].cell == Position(0, 0)
    finally:
        unsubscribe()
