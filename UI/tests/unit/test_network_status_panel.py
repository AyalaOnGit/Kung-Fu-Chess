"""
Unit tests for UI/ui_components/network_status_panel.py.
"""
import sys
import pathlib

ui_dir = pathlib.Path(__file__).parent.parent.parent
if str(ui_dir) not in sys.path:
    sys.path.insert(0, str(ui_dir))

import server_bridge  # noqa: F401

from kungfu_chess.model.piece import Color
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece, Kind
from state.game_events import GameOver, MoveAccepted, OpponentDisconnected
from ui_components.network_status_panel import NetworkStatusPanel


def test_no_message_before_any_disconnect():
    panel = NetworkStatusPanel()
    assert panel.get_status_message() is None


def test_opponent_disconnected_starts_a_countdown_message():
    panel = NetworkStatusPanel()
    panel.on_event(OpponentDisconnected(grace_seconds=20.0))
    assert panel.get_status_message() == 'Opponent disconnected -- auto-resign in 20s'


def test_countdown_decreases_as_time_passes():
    panel = NetworkStatusPanel()
    panel.on_event(OpponentDisconnected(grace_seconds=20.0))
    panel.tick(5000.0)
    assert panel.get_status_message() == 'Opponent disconnected -- auto-resign in 15s'


def test_countdown_does_not_go_negative():
    panel = NetworkStatusPanel()
    panel.on_event(OpponentDisconnected(grace_seconds=5.0))
    panel.tick(999999.0)
    assert panel.get_status_message() == 'Opponent disconnected -- auto-resign in 0s'


def test_any_other_game_event_clears_the_countdown():
    panel = NetworkStatusPanel()
    panel.on_event(OpponentDisconnected(grace_seconds=20.0))
    piece = Piece(id=1, color=Color.WHITE, kind=Kind.PAWN, cell=Position(4, 4))
    panel.on_event(MoveAccepted(piece=piece, src_pos=Position(6, 4), dst_pos=Position(4, 4)))
    assert panel.get_status_message() is None


def test_game_over_clears_the_countdown():
    panel = NetworkStatusPanel()
    panel.on_event(OpponentDisconnected(grace_seconds=20.0))
    panel.on_event(GameOver(winner=Color.WHITE, loser=Color.BLACK))
    assert panel.get_status_message() is None


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
