"""
Unit tests for UI/ui_components/score_panel.py's ScorePanel.
"""
from kungfu_chess.model.piece import Piece, Color, Kind
from kungfu_chess.model.position import Position
from state.game_events import PieceCaptured, GameOver
from ui_components.score_panel import ScorePanel


def _captured_event(captured_kind, captured_color, capturer=None):
    captured = Piece(id=1, color=captured_color, kind=captured_kind, cell=Position(0, 0))
    return PieceCaptured(piece=captured, capturer=capturer, pos=Position(0, 0))


def test_initial_scores_are_zero():
    panel = ScorePanel()
    assert panel.get_score(Color.WHITE) == 0
    assert panel.get_score(Color.BLACK) == 0
    assert panel.get_captured(Color.WHITE) == []


def test_capture_credits_the_capturers_color():
    panel = ScorePanel()
    capturer = Piece(id=2, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 3))

    panel.on_event(_captured_event(Kind.PAWN, Color.BLACK, capturer=capturer))

    assert panel.get_score(Color.WHITE) == ScorePanel.PIECE_VALUES[Kind.PAWN]
    assert panel.get_score(Color.BLACK) == 0
    assert panel.get_captured(Color.WHITE) == [Kind.PAWN]


def test_capture_with_no_capturer_credits_the_opponent_of_the_captured_piece():
    """e.g. an airborne-jump capture where the arriving piece was the one
    removed -- capturer=None, so credit goes to the captured piece's
    opponent color."""
    panel = ScorePanel()

    panel.on_event(_captured_event(Kind.PAWN, Color.WHITE, capturer=None))

    assert panel.get_score(Color.BLACK) == ScorePanel.PIECE_VALUES[Kind.PAWN]
    assert panel.get_captured(Color.BLACK) == [Kind.PAWN]


def test_scores_accumulate_across_captures():
    panel = ScorePanel()
    capturer = Piece(id=2, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 3))

    panel.on_event(_captured_event(Kind.PAWN, Color.BLACK, capturer=capturer))
    panel.on_event(_captured_event(Kind.KNIGHT, Color.BLACK, capturer=capturer))

    expected = ScorePanel.PIECE_VALUES[Kind.PAWN] + ScorePanel.PIECE_VALUES[Kind.KNIGHT]
    assert panel.get_score(Color.WHITE) == expected
    assert panel.get_captured(Color.WHITE) == [Kind.PAWN, Kind.KNIGHT]


def test_get_captured_returns_a_copy():
    panel = ScorePanel()
    capturer = Piece(id=2, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 3))
    panel.on_event(_captured_event(Kind.PAWN, Color.BLACK, capturer=capturer))

    result = panel.get_captured(Color.WHITE)
    result.append(Kind.QUEEN)

    assert panel.get_captured(Color.WHITE) == [Kind.PAWN]


def test_other_events_are_ignored():
    panel = ScorePanel()
    panel.on_event(GameOver(winner=Color.WHITE, loser=Color.BLACK))
    assert panel.get_score(Color.WHITE) == 0
