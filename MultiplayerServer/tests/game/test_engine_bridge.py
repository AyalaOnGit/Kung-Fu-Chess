import asyncio

import pytest

from core.bus import AsyncMessageBus
from game.engine_bridge import EngineEventRelay
from game.engine_factory import build_game_stack
from game.events import GameOver, PieceArrived, PieceCaptured

from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece, Color, Kind
from kungfu_chess.model.position import Position
from kungfu_chess.engine.commands import MoveCommand


def _two_king_board(**extra_pieces: Piece) -> Board:
    board = Board(width=8, height=8)
    board.add_piece(Piece(id=100, color=Color.WHITE, kind=Kind.KING, cell=Position(7, 7)))
    board.add_piece(Piece(id=101, color=Color.BLACK, kind=Kind.KING, cell=Position(7, 0)))
    for piece in extra_pieces.values():
        board.add_piece(piece)
    return board


@pytest.mark.asyncio
async def test_tick_with_no_motion_publishes_nothing():
    board = _two_king_board()
    engine = build_game_stack(board)
    bus = AsyncMessageBus()
    relay = EngineEventRelay(engine, bus, topic='room:test')

    received = []

    async def handler(event):
        received.append(event)

    unsubscribe = bus.subscribe('room:test', handler)
    try:
        engine.wait(100)
        relay.tick()
        await asyncio.sleep(0.05)
        assert received == []
    finally:
        unsubscribe()


@pytest.mark.asyncio
async def test_tick_publishes_piece_arrived_once_motion_completes():
    board = _two_king_board(rook=Piece(id=1, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0)))
    engine = build_game_stack(board)
    bus = AsyncMessageBus()
    relay = EngineEventRelay(engine, bus, topic='room:test')

    received = []
    got_it = asyncio.Event()

    async def handler(event):
        received.append(event)
        got_it.set()

    unsubscribe = bus.subscribe('room:test', handler)
    try:
        result = engine.execute(MoveCommand(Position(0, 0), Position(0, 3)))
        assert result.is_accepted

        engine.wait(3000)  # 3 cells * 1000ms/cell (CELL_SIZE_PX / PIECE_SPEED_PPS)
        relay.tick()

        await asyncio.wait_for(got_it.wait(), timeout=1.0)
        assert len(received) == 1
        assert isinstance(received[0], PieceArrived)
        assert received[0].piece.kind is Kind.ROOK
        assert received[0].pos == Position(0, 3)
    finally:
        unsubscribe()


@pytest.mark.asyncio
async def test_tick_publishes_capture_and_game_over_when_king_is_captured():
    board = _two_king_board(rook=Piece(id=1, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0)))
    # Put the black king directly in the rook's path instead of its usual corner.
    board.remove_piece(Position(7, 0))
    board.add_piece(Piece(id=101, color=Color.BLACK, kind=Kind.KING, cell=Position(0, 3)))

    engine = build_game_stack(board)
    bus = AsyncMessageBus()
    relay = EngineEventRelay(engine, bus, topic='room:test')

    received = []
    saw_game_over = asyncio.Event()

    async def handler(event):
        received.append(event)
        if isinstance(event, GameOver):
            saw_game_over.set()

    unsubscribe = bus.subscribe('room:test', handler)
    try:
        result = engine.execute(MoveCommand(Position(0, 0), Position(0, 3)))
        assert result.is_accepted

        engine.wait(3000)
        relay.tick()

        await asyncio.wait_for(saw_game_over.wait(), timeout=1.0)

        captures = [e for e in received if isinstance(e, PieceCaptured)]
        game_overs = [e for e in received if isinstance(e, GameOver)]
        assert len(captures) == 1
        assert captures[0].piece.kind is Kind.KING
        assert captures[0].piece.color is Color.BLACK
        assert len(game_overs) == 1
        assert game_overs[0].winner is Color.WHITE
        assert game_overs[0].loser is Color.BLACK
        assert engine.game_over
    finally:
        unsubscribe()
