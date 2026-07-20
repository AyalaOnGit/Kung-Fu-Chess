import json

import pytest

from game.events import GameOver, JumpAccepted, MoveAccepted, PieceArrived, PieceCaptured, Promotion
from game.wire import to_wire

from kungfu_chess.model.piece import Piece, Color, Kind
from kungfu_chess.model.position import Position


def _piece(id_=1, color=Color.WHITE, kind=Kind.ROOK, row=0, col=0) -> Piece:
    return Piece(id=id_, color=color, kind=kind, cell=Position(row, col))


def _assert_json_safe(data: dict) -> None:
    # Round-tripping through json.dumps is the proxy for "no kungfu_chess
    # object leaked through" — a Piece/Position/Enum would raise TypeError.
    json.dumps(data)


def test_move_accepted_to_wire():
    piece = _piece()
    event_type, data = to_wire(MoveAccepted(piece=piece, src=Position(0, 0), dest=Position(0, 3)))

    assert event_type == 'move_accepted'
    assert data == {
        'piece': {'id': 1, 'color': 'w', 'kind': 'R', 'cell': [0, 0]},
        'src': [0, 0],
        'dest': [0, 3],
    }
    _assert_json_safe(data)


def test_jump_accepted_to_wire():
    piece = _piece(kind=Kind.KNIGHT)
    event_type, data = to_wire(JumpAccepted(piece=piece, cell=Position(2, 1)))

    assert event_type == 'jump_accepted'
    assert data == {'piece': {'id': 1, 'color': 'w', 'kind': 'N', 'cell': [0, 0]}, 'cell': [2, 1]}
    _assert_json_safe(data)


def test_piece_arrived_to_wire():
    piece = _piece()
    event_type, data = to_wire(PieceArrived(piece=piece, pos=Position(0, 3)))

    assert event_type == 'piece_arrived'
    assert data['pos'] == [0, 3]
    _assert_json_safe(data)


def test_piece_captured_to_wire_with_capturer():
    captured = _piece(id_=2, color=Color.BLACK, kind=Kind.KING, row=0, col=3)
    capturer = _piece(id_=1, color=Color.WHITE, kind=Kind.ROOK, row=0, col=3)
    event_type, data = to_wire(PieceCaptured(piece=captured, capturer=capturer, pos=Position(0, 3)))

    assert event_type == 'piece_captured'
    assert data['piece']['color'] == 'b'
    assert data['capturer']['color'] == 'w'
    _assert_json_safe(data)


def test_piece_captured_to_wire_without_capturer():
    captured = _piece(id_=2, color=Color.BLACK, kind=Kind.KING)
    event_type, data = to_wire(PieceCaptured(piece=captured, capturer=None, pos=Position(0, 0)))

    assert data['capturer'] is None
    _assert_json_safe(data)


def test_promotion_to_wire():
    piece = _piece(kind=Kind.QUEEN, row=0)
    event_type, data = to_wire(Promotion(piece=piece, old_kind=Kind.PAWN, new_kind=Kind.QUEEN))

    assert event_type == 'promotion'
    assert data == {
        'piece': {'id': 1, 'color': 'w', 'kind': 'Q', 'cell': [0, 0]},
        'old_kind': 'P',
        'new_kind': 'Q',
    }
    _assert_json_safe(data)


def test_game_over_to_wire():
    event_type, data = to_wire(GameOver(winner=Color.WHITE, loser=Color.BLACK))

    assert event_type == 'game_over'
    assert data == {'winner': 'w', 'loser': 'b'}
    _assert_json_safe(data)


def test_unknown_event_type_raises():
    with pytest.raises(ValueError):
        to_wire(object())
