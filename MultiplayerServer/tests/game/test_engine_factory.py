from game.engine_factory import build_game_stack

from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece, Color, Kind
from kungfu_chess.model.position import Position


def test_default_board_is_the_standard_starting_position():
    engine = build_game_stack()
    assert len(engine.board.all_pieces()) == 32
    assert not engine.game_over


def test_explicit_board_is_used_as_is():
    board = Board(width=8, height=8)
    board.add_piece(Piece(id=1, color=Color.WHITE, kind=Kind.KING, cell=Position(0, 0)))
    board.add_piece(Piece(id=2, color=Color.BLACK, kind=Kind.KING, cell=Position(7, 7)))

    engine = build_game_stack(board)

    assert engine.board is board
    assert len(engine.board.all_pieces()) == 2


def test_returned_engine_is_ready_to_execute_commands():
    from kungfu_chess.engine.commands import MoveCommand

    board = Board(width=8, height=8)
    board.add_piece(Piece(id=1, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0)))
    board.add_piece(Piece(id=2, color=Color.WHITE, kind=Kind.KING, cell=Position(7, 0)))
    board.add_piece(Piece(id=3, color=Color.BLACK, kind=Kind.KING, cell=Position(7, 7)))

    engine = build_game_stack(board)
    result = engine.execute(MoveCommand(Position(0, 0), Position(0, 3)))

    assert result.is_accepted
