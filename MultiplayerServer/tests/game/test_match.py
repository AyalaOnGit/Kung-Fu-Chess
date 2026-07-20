import asyncio

import pytest

from core.bus import AsyncMessageBus
from game.engine_factory import build_game_stack
from game.events import PieceArrived
from game.match import TOPIC, MatchSession
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


def test_default_construction_uses_the_standard_starting_board():
    match = MatchSession(AsyncMessageBus())
    assert len(match.engine.board.all_pieces()) == 32
    assert not match.is_running


def test_explicit_engine_is_used_as_is():
    engine = build_game_stack(_minimal_board())
    match = MatchSession(AsyncMessageBus(), engine=engine)
    assert match.engine is engine


@pytest.mark.asyncio
async def test_start_marks_the_session_running():
    match = MatchSession(AsyncMessageBus(), engine=build_game_stack(_minimal_board()), tick_interval_ms=10)
    match.start()
    try:
        assert match.is_running
    finally:
        await match.stop()


@pytest.mark.asyncio
async def test_starting_twice_raises():
    match = MatchSession(AsyncMessageBus(), engine=build_game_stack(_minimal_board()), tick_interval_ms=10)
    match.start()
    try:
        with pytest.raises(RuntimeError):
            match.start()
    finally:
        await match.stop()


@pytest.mark.asyncio
async def test_stop_without_start_is_a_noop():
    match = MatchSession(AsyncMessageBus(), engine=build_game_stack(_minimal_board()))
    await match.stop()  # must not raise
    assert not match.is_running


@pytest.mark.asyncio
async def test_stop_is_idempotent():
    match = MatchSession(AsyncMessageBus(), engine=build_game_stack(_minimal_board()), tick_interval_ms=10)
    match.start()
    await match.stop()
    await match.stop()  # must not raise
    assert not match.is_running


@pytest.mark.asyncio
async def test_stop_cancels_the_tick_task_and_leaves_no_lingering_task():
    match = MatchSession(AsyncMessageBus(), engine=build_game_stack(_minimal_board()), tick_interval_ms=10)

    tasks_before = asyncio.all_tasks()
    match.start()
    await asyncio.sleep(0.03)
    assert asyncio.all_tasks() - tasks_before  # the tick task is really out there

    await match.stop()
    await asyncio.sleep(0)  # let cancellation fully propagate
    assert asyncio.all_tasks() - tasks_before == set()


def test_handle_move_delegates_to_commands_and_engine():
    match = MatchSession(AsyncMessageBus(), engine=build_game_stack(_minimal_board()))
    session = ClientSession.new(websocket=None, role=Role.WHITE)

    result = match.handle_move(session, {'src': [0, 0], 'dest': [0, 3]})

    assert result.accepted
    # Real-time engine: acceptance starts the motion, it doesn't teleport
    # the piece — the board only updates on arrival (a later tick).
    moving_piece = match.engine.board.piece_at(Position(0, 0))
    assert moving_piece is not None
    assert moving_piece.state.value == 'moving'


def test_handle_jump_delegates_to_commands_and_engine():
    match = MatchSession(AsyncMessageBus(), engine=build_game_stack(_minimal_board()))
    session = ClientSession.new(websocket=None, role=Role.WHITE)

    result = match.handle_jump(session, {'cell': [0, 0]})

    assert result.accepted


@pytest.mark.asyncio
async def test_on_game_over_fires_with_winner_and_loser_roles_once_king_is_captured():
    board = Board(width=8, height=8)
    board.add_piece(Piece(id=1, color=Color.WHITE, kind=Kind.KING, cell=Position(7, 7)))
    board.add_piece(Piece(id=2, color=Color.BLACK, kind=Kind.KING, cell=Position(0, 3)))
    board.add_piece(Piece(id=3, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0)))

    calls = []

    async def on_game_over(winner_role, loser_role):
        calls.append((winner_role, loser_role))

    match = MatchSession(AsyncMessageBus(), engine=build_game_stack(board),
                          tick_interval_ms=20, on_game_over=on_game_over)
    session = ClientSession.new(websocket=None, role=Role.WHITE)

    try:
        match.start()
        result = match.handle_move(session, {'src': [0, 0], 'dest': [0, 3]})
        assert result.accepted

        # Poll instead of a fixed sleep: the tick loop needs ~1000ms of real
        # travel time plus tick slack before the capture actually resolves.
        for _ in range(100):
            if calls:
                break
            await asyncio.sleep(0.05)
    finally:
        await match.stop()

    assert calls == [(Role.WHITE, Role.BLACK)]


@pytest.mark.asyncio
async def test_on_game_over_is_not_called_again_on_later_ticks():
    board = Board(width=8, height=8)
    board.add_piece(Piece(id=1, color=Color.WHITE, kind=Kind.KING, cell=Position(7, 7)))
    board.add_piece(Piece(id=2, color=Color.BLACK, kind=Kind.KING, cell=Position(0, 3)))
    board.add_piece(Piece(id=3, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0)))

    calls = []

    async def on_game_over(winner_role, loser_role):
        calls.append((winner_role, loser_role))

    match = MatchSession(AsyncMessageBus(), engine=build_game_stack(board),
                          tick_interval_ms=20, on_game_over=on_game_over)
    session = ClientSession.new(websocket=None, role=Role.WHITE)

    try:
        match.start()
        match.handle_move(session, {'src': [0, 0], 'dest': [0, 3]})
        for _ in range(100):
            if calls:
                break
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.2)  # several more ticks after game-over
    finally:
        await match.stop()

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_tick_loop_advances_the_engine_and_publishes_events_over_real_time():
    bus = AsyncMessageBus()
    match = MatchSession(bus, engine=build_game_stack(_minimal_board()), tick_interval_ms=20)
    session = ClientSession.new(websocket=None, role=Role.WHITE)

    got_arrival = asyncio.Event()

    async def handler(event):
        if isinstance(event, PieceArrived):
            got_arrival.set()

    unsubscribe = bus.subscribe(TOPIC, handler)
    try:
        match.start()
        result = match.handle_move(session, {'src': [0, 0], 'dest': [0, 1]})
        assert result.accepted

        # 1 cell = 1000ms of travel time (kungfu_chess.config); the tick
        # loop advances real elapsed time each 20ms, so this needs a real
        # wait, not a FakeClock — motion duration is physical time here.
        await asyncio.wait_for(got_arrival.wait(), timeout=2.0)
    finally:
        await match.stop()
        unsubscribe()
