"""
Unit tests for UI/ui_components/halt_flash.py's HaltFlashTracker.
"""
from kungfu_chess.model.piece import Piece, Color, Kind
from kungfu_chess.model.position import Position
from state.game_events import PieceHalted, GameOver
from ui_components.halt_flash import HaltFlashTracker


def _piece():
    return Piece(id=1, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0))


def test_initially_not_flashing():
    tracker = HaltFlashTracker(flash_duration_ms=100)
    assert not tracker.is_flashing()
    assert tracker.get_flashing_piece_id() is None


def test_piece_halted_event_starts_flashing():
    tracker = HaltFlashTracker(flash_duration_ms=100)
    piece = _piece()

    tracker.on_event(PieceHalted(piece=piece, halted_at=Position(0, 2)))

    assert tracker.is_flashing()
    assert tracker.get_flashing_piece_id() == piece.id


def test_other_events_are_ignored():
    tracker = HaltFlashTracker(flash_duration_ms=100)
    tracker.on_event(GameOver(winner=Color.WHITE, loser=Color.BLACK))
    assert not tracker.is_flashing()


def test_tick_before_duration_keeps_flashing():
    tracker = HaltFlashTracker(flash_duration_ms=100)
    tracker.on_event(PieceHalted(piece=_piece(), halted_at=Position(0, 2)))

    tracker.tick(50)

    assert tracker.is_flashing()


def test_tick_past_duration_stops_flashing():
    tracker = HaltFlashTracker(flash_duration_ms=100)
    tracker.on_event(PieceHalted(piece=_piece(), halted_at=Position(0, 2)))

    tracker.tick(150)

    assert not tracker.is_flashing()
    assert tracker.get_flashing_piece_id() is None


def test_tick_with_no_active_halt_does_nothing():
    tracker = HaltFlashTracker(flash_duration_ms=100)
    tracker.tick(1000)  # must not raise
    assert not tracker.is_flashing()


def test_new_halt_restarts_the_flash_timer():
    tracker = HaltFlashTracker(flash_duration_ms=100)
    piece_a = _piece()
    piece_b = Piece(id=2, color=Color.BLACK, kind=Kind.KNIGHT, cell=Position(1, 1))

    tracker.on_event(PieceHalted(piece=piece_a, halted_at=Position(0, 2)))
    tracker.tick(90)
    tracker.on_event(PieceHalted(piece=piece_b, halted_at=Position(1, 3)))
    tracker.tick(90)  # would have expired piece_a's flash, but timer restarted

    assert tracker.is_flashing()
    assert tracker.get_flashing_piece_id() == piece_b.id
