"""
Unit tests for UI/ui_components/moves_log_panel.py's MovesLogPanel.
"""
from kungfu_chess.model.piece import Piece, Color, Kind
from kungfu_chess.model.position import Position
from state.game_events import MoveAccepted, GameOver
from ui_components.moves_log_panel import MovesLogPanel


def _move(color, kind, src, dst):
    piece = Piece(id=1, color=color, kind=kind, cell=dst)
    return MoveAccepted(piece=piece, src_pos=src, dst_pos=dst)


def test_initially_empty():
    panel = MovesLogPanel()
    assert panel.get_moves() == {'white': [], 'black': []}


def test_white_move_recorded_in_white_log():
    panel = MovesLogPanel()
    panel.on_event(_move(Color.WHITE, Kind.ROOK, Position(7, 0), Position(4, 0)))

    moves = panel.get_moves()
    assert len(moves['white']) == 1
    assert moves['black'] == []


def test_black_move_recorded_in_black_log():
    panel = MovesLogPanel()
    panel.on_event(_move(Color.BLACK, Kind.ROOK, Position(0, 0), Position(3, 0)))

    moves = panel.get_moves()
    assert len(moves['black']) == 1
    assert moves['white'] == []


def test_notation_uses_algebraic_columns_and_rows():
    """col 0 -> 'a', row 7 (bottom, white's home rank) -> rank '1'."""
    panel = MovesLogPanel()
    panel.on_event(_move(Color.WHITE, Kind.ROOK, Position(7, 0), Position(4, 0)))

    move_str = panel.get_moves()['white'][0]
    assert move_str.startswith('R')
    assert 'a1-a4' in move_str


def test_moves_accumulate_in_order():
    panel = MovesLogPanel()
    panel.on_event(_move(Color.WHITE, Kind.ROOK, Position(7, 0), Position(4, 0)))
    panel.on_event(_move(Color.WHITE, Kind.ROOK, Position(4, 0), Position(4, 3)))

    assert len(panel.get_moves()['white']) == 2


def test_other_events_are_ignored():
    panel = MovesLogPanel()
    panel.on_event(GameOver(winner=Color.WHITE, loser=Color.BLACK))
    assert panel.get_moves() == {'white': [], 'black': []}
