"""
Unit tests for UI/network/network_game_facade.py.

Uses a fake WsClient (no real socket) since ws_client.py's own networking is
already covered end-to-end by test_ws_client.py -- these tests are about
NetworkGameFacade's wire-event translation and role gating.
"""
import sys
import pathlib

ui_dir = pathlib.Path(__file__).parent.parent.parent
if str(ui_dir) not in sys.path:
    sys.path.insert(0, str(ui_dir))

import server_bridge  # noqa: F401

from kungfu_chess.config import COOLDOWN_MS
from kungfu_chess.interaction.board_mapper import BoardMapper
from kungfu_chess.model.piece import Color, Kind, PieceState
from kungfu_chess.model.position import Position

from network.network_game_facade import NetworkGameFacade
from network.protocol import Envelope
from state.game_events import (
    GameOver, MoveAccepted, OpponentDisconnected, PieceArrived, PieceCaptured, Promotion, RatingUpdate,
)


class _FakeWsClient:
    def __init__(self):
        self.sent = []  # list of (type, data)
        self._queued = []

    def send(self, envelope_type, data=None):
        self.sent.append((envelope_type, data or {}))

    def queue(self, envelope_type, data):
        self._queued.append(Envelope(type=envelope_type, data=data))

    def poll_events(self):
        events, self._queued = self._queued, []
        return events


def _piece_dict(id, color, kind, cell, state='idle', **extra):
    d = {'id': id, 'color': color, 'kind': kind, 'cell': list(cell), 'state': state}
    d.update(extra)
    return d


def _standard_two_king_state():
    """Minimal state_sync-shaped payload: two kings + one white rook."""
    return {
        'pieces': [
            _piece_dict(1, 'w', 'K', (7, 4)),
            _piece_dict(2, 'b', 'K', (0, 4)),
            _piece_dict(3, 'w', 'R', (7, 0)),
        ],
        'game_over': False,
        'clock_ms': 0,
    }


def _mapper():
    return BoardMapper(width=8, height=8, offset_x=0, offset_y=0)


def _facade(role='white', state=None, ws=None):
    ws = ws or _FakeWsClient()
    facade = NetworkGameFacade(ws, _mapper(), state or _standard_two_king_state(), role)
    return facade, ws


def test_initial_state_seeds_the_mirror_board():
    facade, _ = _facade()
    assert len(facade.board.all_pieces()) == 3
    rook = facade.board.piece_at(Position(7, 0))
    assert rook is not None and rook.kind is Kind.ROOK and rook.color is Color.WHITE


def test_viewer_cannot_select_or_move_a_piece():
    facade, ws = _facade(role='viewer')
    # rook at (7,0) -> pixel (0*100, 7*100) with offset 0 -> (0, 700)
    handled = facade.request_click(10, 710)
    assert handled is False
    assert facade.get_selected_pos() is None
    assert ws.sent == []


def test_cannot_select_opponents_piece():
    facade, ws = _facade(role='black')
    facade.request_click(10, 710)  # white rook at (7,0)
    assert facade.get_selected_pos() is None
    assert ws.sent == []


def test_selecting_own_piece_then_clicking_a_destination_sends_a_move_command():
    facade, ws = _facade(role='white')
    facade.request_click(10, 710)  # select white rook at (7,0)
    assert facade.get_selected_pos() == Position(7, 0)

    handled = facade.request_click(10, 410)  # click (7,4)? use a clearly empty far cell
    assert handled is True
    assert facade.get_selected_pos() is None
    assert ws.sent == [('move', {'src': [7, 0], 'dest': [4, 0]})]


def test_move_accepted_starts_a_pending_motion_and_publishes_event():
    facade, ws = _facade(role='white')
    events = []
    facade.subscribe(events.append)

    ws.queue('move_accepted', {
        'piece': _piece_dict(3, 'w', 'R', (7, 0)), 'src': [7, 0], 'dest': [4, 0],
    })
    facade.tick(16.0)

    assert len(events) == 1
    assert isinstance(events[0], MoveAccepted)
    piece = facade.board.piece_at(Position(7, 0))  # not relocated yet
    assert piece is not None
    assert piece.state is PieceState.MOVING
    assert facade.get_pending_motion(3) is not None


def test_piece_arrived_relocates_the_piece_and_starts_cooldown():
    facade, ws = _facade(role='white')
    events = []
    facade.subscribe(events.append)

    ws.queue('move_accepted', {'piece': _piece_dict(3, 'w', 'R', (7, 0)), 'src': [7, 0], 'dest': [4, 0]})
    facade.tick(16.0)
    ws.queue('piece_arrived', {'piece': _piece_dict(3, 'w', 'R', (7, 0)), 'pos': [4, 0]})
    facade.tick(16.0)

    assert facade.board.piece_at(Position(7, 0)) is None
    moved = facade.board.piece_at(Position(4, 0))
    assert moved is not None and moved.id == 3
    assert moved.state is PieceState.COOLING
    assert facade.get_cooldown_ratio(moved) > 0.0
    assert any(isinstance(e, PieceArrived) for e in events)


def test_cooldown_expires_back_to_idle_after_cooldown_ms():
    facade, ws = _facade(role='white')
    ws.queue('move_accepted', {'piece': _piece_dict(3, 'w', 'R', (7, 0)), 'src': [7, 0], 'dest': [4, 0]})
    facade.tick(16.0)
    ws.queue('piece_arrived', {'piece': _piece_dict(3, 'w', 'R', (7, 0)), 'pos': [4, 0]})
    facade.tick(16.0)

    piece = facade.board.piece_at(Position(4, 0))
    assert piece.state is PieceState.COOLING

    facade.tick(COOLDOWN_MS + 10)
    assert piece.state is PieceState.IDLE
    assert facade.get_cooldown_ratio(piece) == 0.0


def test_piece_captured_publishes_event_without_double_mutating_the_board():
    facade, ws = _facade(role='white')
    events = []
    facade.subscribe(events.append)

    # White rook captures the black king by arriving on its square.
    ws.queue('move_accepted', {'piece': _piece_dict(3, 'w', 'R', (7, 0)), 'src': [7, 0], 'dest': [0, 4]})
    facade.tick(16.0)
    ws.queue('piece_arrived', {'piece': _piece_dict(3, 'w', 'R', (7, 0)), 'pos': [0, 4]})
    ws.queue('piece_captured', {
        'piece': _piece_dict(2, 'b', 'K', (0, 4)),
        'capturer': _piece_dict(3, 'w', 'R', (0, 4)),
        'pos': [0, 4],
    })
    facade.tick(16.0)

    capturer_on_board = facade.board.piece_at(Position(0, 4))
    assert capturer_on_board is not None and capturer_on_board.id == 3  # capture didn't corrupt the board
    captured_events = [e for e in events if isinstance(e, PieceCaptured)]
    assert len(captured_events) == 1
    assert captured_events[0].piece.kind is Kind.KING
    assert captured_events[0].capturer.id == 3


def test_promotion_updates_piece_kind_and_publishes_event():
    state = {
        'pieces': [
            _piece_dict(1, 'w', 'K', (7, 4)),
            _piece_dict(2, 'b', 'K', (0, 4)),
            _piece_dict(4, 'w', 'P', (0, 1)),
        ],
        'game_over': False, 'clock_ms': 0,
    }
    facade, ws = _facade(role='white', state=state)
    events = []
    facade.subscribe(events.append)

    ws.queue('promotion', {'piece': _piece_dict(4, 'w', 'P', (0, 1)), 'old_kind': 'P', 'new_kind': 'Q'})
    facade.tick(16.0)

    pawn = facade.board.piece_at(Position(0, 1))
    assert pawn.kind is Kind.QUEEN
    assert any(isinstance(e, Promotion) and e.new_kind is Kind.QUEEN for e in events)


def test_game_over_publishes_event():
    facade, ws = _facade()
    events = []
    facade.subscribe(events.append)

    ws.queue('game_over', {'winner': 'w', 'loser': 'b'})
    facade.tick(16.0)

    assert events == [GameOver(winner=Color.WHITE, loser=Color.BLACK)]


def test_rating_update_publishes_event():
    facade, ws = _facade()
    events = []
    facade.subscribe(events.append)

    ws.queue('rating_update', {
        'white_elo_before': 1200, 'white_elo_after': 1216,
        'black_elo_before': 1200, 'black_elo_after': 1184,
    })
    facade.tick(16.0)

    assert events == [RatingUpdate(white_elo_before=1200, white_elo_after=1216,
                                    black_elo_before=1200, black_elo_after=1184)]


def test_opponent_disconnected_publishes_event_with_grace_seconds():
    facade, ws = _facade()
    events = []
    facade.subscribe(events.append)

    ws.queue('opponent_disconnected', {'grace_seconds': 20.0})
    facade.tick(16.0)

    assert events == [OpponentDisconnected(grace_seconds=20.0)]


def test_state_sync_resync_mutates_the_board_in_place():
    """A renderer holds a direct reference to facade.board, captured once at
    game-screen setup -- a resync must never rebind self._board to a new
    object, or the renderer would keep drawing a stale snapshot forever."""
    facade, ws = _facade(role='white')
    board_reference = facade.board

    new_state = {
        'pieces': [
            _piece_dict(1, 'w', 'K', (7, 4)),
            _piece_dict(2, 'b', 'K', (0, 4)),
            _piece_dict(5, 'w', 'Q', (3, 3)),  # different piece set than the initial state
        ],
        'game_over': False, 'clock_ms': 1000,
    }
    ws.queue('state_sync', {'role': 'white', 'room_id': 'room-1', 'state': new_state})
    facade.tick(16.0)

    assert facade.board is board_reference  # same object identity
    assert len(facade.board.all_pieces()) == 3
    queen = facade.board.piece_at(Position(3, 3))
    assert queen is not None and queen.kind is Kind.QUEEN
    assert facade.board.piece_at(Position(7, 0)) is None  # old rook is gone


def test_unrecognized_envelope_types_are_ignored_without_error():
    facade, ws = _facade()
    ws.queue('accepted', {})
    ws.queue('pong', {})
    facade.tick(16.0)  # must not raise


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
