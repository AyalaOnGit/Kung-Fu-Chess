import json

import pytest

from game.engine_factory import build_game_stack
from game.events import GameOver, JumpAccepted, MoveAccepted, PieceArrived, PieceCaptured, Promotion
from game.wire import state_sync_payload, to_wire

from kungfu_chess.engine.commands import MoveCommand
from kungfu_chess.model.board import Board
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


# --- state_sync_payload ---

def _board_with_a_rook() -> Board:
    board = Board(width=8, height=8)
    board.add_piece(Piece(id=1, color=Color.WHITE, kind=Kind.KING, cell=Position(7, 7)))
    board.add_piece(Piece(id=2, color=Color.BLACK, kind=Kind.KING, cell=Position(7, 0)))
    board.add_piece(Piece(id=3, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0)))
    return board


def test_state_sync_payload_includes_every_piece_and_top_level_fields():
    engine = build_game_stack(_board_with_a_rook())

    payload = state_sync_payload(engine)

    assert payload['game_over'] is False
    assert payload['clock_ms'] == 0
    assert len(payload['pieces']) == 3
    rook = next(p for p in payload['pieces'] if p['kind'] == 'R')
    assert rook == {'id': 3, 'color': 'w', 'kind': 'R', 'cell': [0, 0], 'state': 'idle'}
    _assert_json_safe(payload)


def test_state_sync_payload_includes_cooldown_ratio_only_for_cooling_pieces():
    engine = build_game_stack(_board_with_a_rook())
    engine.execute(MoveCommand(Position(0, 0), Position(0, 3)))
    engine.wait(3000)  # completes the move, piece enters cooldown

    payload = state_sync_payload(engine)

    rook = next(p for p in payload['pieces'] if p['kind'] == 'R')
    assert rook['state'] == 'cooling'
    assert 0.0 <= rook['cooldown_ratio'] <= 1.0

    king = next(p for p in payload['pieces'] if p['id'] == 1)
    assert king['state'] == 'idle'
    assert 'cooldown_ratio' not in king
    _assert_json_safe(payload)


def test_state_sync_payload_reflects_game_over():
    engine = build_game_stack(_board_with_a_rook())
    engine.force_game_over()

    assert state_sync_payload(engine)['game_over'] is True
