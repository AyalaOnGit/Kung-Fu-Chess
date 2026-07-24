"""
Unit tests for UI/network/network_game_facade.py.

Uses a fake WsClient (no real socket) since ws_client.py's own networking is
already covered end-to-end by test_ws_client.py -- these tests are about
NetworkGameFacade's wire-event translation and role gating.
"""
import pytest

from kungfu_chess.config import COOLDOWN_MS, JUMP_DURATION_MS
from kungfu_chess.interaction.board_mapper import BoardMapper
from kungfu_chess.model.piece import Color, Kind, PieceState
from kungfu_chess.model.position import Position

from network.network_game_facade import NetworkGameFacade, _STALE_MOTION_GRACE_MS
from network.protocol import Envelope
from state.game_events import (
    GameOver, MoveAccepted, OpponentDisconnected, OpponentJoined, PieceArrived, PieceCaptured,
    Promotion, RatingUpdate,
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


def _facade(role='white', state=None, ws=None, opponent_present=True):
    ws = ws or _FakeWsClient()
    facade = NetworkGameFacade(ws, _mapper(), state or _standard_two_king_state(), role,
                                opponent_present=opponent_present)
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


def test_cannot_select_a_piece_while_waiting_for_opponent():
    """The room's creator, still alone in the room, must not be able to
    select or move any piece -- not even their own -- until the second
    seat is filled."""
    facade, ws = _facade(role='white', opponent_present=False)
    handled = facade.request_click(10, 710)  # own rook at (7,0)
    assert handled is False
    assert facade.get_selected_pos() is None
    assert ws.sent == []


def test_cannot_jump_while_waiting_for_opponent():
    facade, ws = _facade(role='white', opponent_present=False)
    facade.request_jump(10, 710)  # own rook at (7,0)
    assert ws.sent == []


def test_opponent_joined_unblocks_interaction():
    facade, ws = _facade(role='white', opponent_present=False)
    ws.queue('opponent_joined', {'role': 'black', 'username': 'bob', 'elo': 1200})
    facade.tick(16.0)

    facade.request_click(10, 710)  # select own rook at (7,0), now allowed
    assert facade.get_selected_pos() == Position(7, 0)

    handled = facade.request_click(10, 410)  # destination click
    assert handled is True
    assert ws.sent == [('move', {'src': [7, 0], 'dest': [4, 0]})]


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


def test_airborne_capture_removes_the_intercepted_piece_from_the_board():
    """A jump doesn't relocate the jumper -- it intercepts an enemy that
    tries to arrive on the jumper's cell mid-air. The intercepted piece
    never gets a paired piece_arrived (it vanishes mid-flight, never
    landing anywhere), so without an explicit removal here nothing would
    ever clean it off this mirror board -- it would render frozen at its
    destination underneath the jumper forever."""
    state = {
        'pieces': [
            _piece_dict(1, 'w', 'K', (7, 4)),
            _piece_dict(2, 'b', 'K', (0, 4)),
            _piece_dict(3, 'w', 'R', (7, 0)),  # jumps
            _piece_dict(4, 'b', 'R', (7, 3)),  # attacks into (7,0), gets intercepted
        ],
        'game_over': False,
        'clock_ms': 0,
    }
    facade, ws = _facade(role='white', state=state)
    events = []
    facade.subscribe(events.append)

    ws.queue('jump_accepted', {'piece': _piece_dict(3, 'w', 'R', (7, 0)), 'cell': [7, 0]})
    ws.queue('move_accepted', {'piece': _piece_dict(4, 'b', 'R', (7, 3)), 'src': [7, 3], 'dest': [7, 0]})
    facade.tick(16.0)
    # The wire reports the intercepted piece at its own original cell --
    # it never arrived anywhere else.
    ws.queue('piece_captured', {
        'piece': _piece_dict(4, 'b', 'R', (7, 3)), 'capturer': None, 'pos': [7, 3],
    })
    facade.tick(16.0)

    assert facade.board.piece_at(Position(7, 3)) is None  # intercepted piece is gone
    assert facade.board.piece_at(Position(7, 0)).id == 3  # jumper untouched, still there
    assert facade.get_pending_motion(4) is None  # no leftover animation for the vanished piece
    captured_events = [e for e in events if isinstance(e, PieceCaptured)]
    assert len(captured_events) == 1
    assert captured_events[0].piece.id == 4


def test_uneventful_jump_settles_back_to_idle_after_its_duration():
    """Most jumps intercept nothing -- the server never sends any follow-up
    event for one that simply completes. Without this client-side timeout
    (mirroring what RealTimeArbiter itself does authoritatively), the piece
    and its animation would stay stuck showing JUMPING forever."""
    facade, ws = _facade(role='white')
    rook = facade.board.piece_at(Position(7, 0))

    ws.queue('jump_accepted', {'piece': _piece_dict(3, 'w', 'R', (7, 0)), 'cell': [7, 0]})
    facade.tick(16.0)
    assert rook.state is PieceState.JUMPING
    assert facade.get_pending_motion(3) is not None

    facade.tick(JUMP_DURATION_MS + _STALE_MOTION_GRACE_MS + 1.0)

    assert rook.state is PieceState.IDLE
    assert facade.get_pending_motion(3) is None


def test_move_with_no_confirming_event_settles_back_to_idle_eventually():
    """A 1-cell move fully blocked by a friendly at the last instant is
    settled back to idle silently server-side (kungfu_chess.realtime's
    RealTimeArbiter only redirects multi-cell paths early enough to still
    resolve via a normal arrival) -- no piece_arrived, no piece_captured,
    nothing on the wire at all. Without this safety net the piece would
    appear to complete a move it never actually made, then stay frozen
    there indefinitely."""
    facade, ws = _facade(role='white')
    rook = facade.board.piece_at(Position(7, 0))

    ws.queue('move_accepted', {'piece': _piece_dict(3, 'w', 'R', (7, 0)), 'src': [7, 0], 'dest': [7, 1]})
    facade.tick(16.0)
    assert rook.state is PieceState.MOVING

    facade.tick(1000.0 + _STALE_MOTION_GRACE_MS + 1.0)  # 1-cell move duration + grace

    assert rook.state is PieceState.IDLE
    assert facade.get_pending_motion(3) is None
    assert facade.board.piece_at(Position(7, 0)).id == 3  # never actually relocated


def test_in_flight_motion_is_not_cleared_before_its_duration_plus_grace():
    """Regression guard for the stale-motion safety net itself: a
    still-legitimately-in-flight motion must not get force-cleared early."""
    facade, ws = _facade(role='white')

    ws.queue('move_accepted', {'piece': _piece_dict(3, 'w', 'R', (7, 0)), 'src': [7, 0], 'dest': [7, 3]})  # 3000ms
    facade.tick(16.0)

    facade.tick(2000.0)  # well within 3000ms + grace

    assert facade.get_pending_motion(3) is not None
    assert facade.board.piece_at(Position(7, 0)).state is PieceState.MOVING


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


def test_opponent_joined_publishes_event_with_role_username_and_elo():
    facade, ws = _facade()
    events = []
    facade.subscribe(events.append)

    ws.queue('opponent_joined', {'role': 'black', 'username': 'bob', 'elo': 1200})
    facade.tick(16.0)

    assert events == [OpponentJoined(role='black', username='bob', elo=1200)]


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


def test_my_color_reflects_the_assigned_role():
    white_facade, _ = _facade(role='white')
    black_facade, _ = _facade(role='black')
    viewer_facade, _ = _facade(role='viewer')

    assert white_facade.my_color is Color.WHITE
    assert black_facade.my_color is Color.BLACK
    assert viewer_facade.my_color is None


def test_initial_state_seeds_cooldown_for_an_already_cooling_piece():
    """A resync/rejoin can hand us a piece that's already mid-cooldown --
    _seed_cooldowns must recreate that remaining cooldown immediately, not
    just for cooldowns that start after construction."""
    state = {
        'pieces': [
            _piece_dict(1, 'w', 'K', (7, 4)),
            _piece_dict(2, 'b', 'K', (0, 4)),
            _piece_dict(3, 'w', 'R', (7, 0), state='cooling', cooldown_ratio=0.5),
        ],
        'game_over': False, 'clock_ms': 0,
    }
    facade, _ = _facade(role='white', state=state)
    rook = facade.board.piece_at(Position(7, 0))

    assert facade.get_cooldown_ratio(rook) == pytest.approx(0.5)


def test_reselecting_a_different_friendly_piece_switches_selection_instead_of_moving():
    facade, ws = _facade(role='white')
    facade.request_click(10, 710)  # select white rook at (7,0)
    assert facade.get_selected_pos() == Position(7, 0)

    # King is also white and sits at (7,4) -> pixel (col*100, row*100) = (400, 700).
    # Clicking it should reselect, not attempt a move.
    handled = facade.request_click(400, 710)

    assert handled is False
    assert facade.get_selected_pos() == Position(7, 4)
    assert ws.sent == []


def test_request_jump_sends_a_jump_command_for_an_own_piece():
    facade, ws = _facade(role='white')
    facade.request_jump(10, 710)  # own rook at (7,0)
    assert ws.sent == [('jump', {'cell': [7, 0]})]


def test_request_jump_on_empty_cell_is_a_no_op():
    facade, ws = _facade(role='white')
    facade.request_jump(10, 410)  # empty cell
    assert ws.sent == []


def test_request_jump_on_opponents_piece_is_a_no_op():
    facade, ws = _facade(role='black')
    facade.request_jump(10, 710)  # white rook
    assert ws.sent == []


def test_move_accepted_for_an_unknown_piece_id_is_ignored():
    facade, ws = _facade(role='white')
    events = []
    facade.subscribe(events.append)

    ws.queue('move_accepted', {'piece': _piece_dict(999, 'w', 'R', (7, 0)), 'src': [7, 0], 'dest': [4, 0]})
    facade.tick(16.0)  # must not raise

    assert events == []


def test_jump_accepted_for_an_unknown_piece_id_is_ignored():
    facade, ws = _facade(role='white')
    events = []
    facade.subscribe(events.append)

    ws.queue('jump_accepted', {'piece': _piece_dict(999, 'w', 'R', (7, 0)), 'cell': [7, 0]})
    facade.tick(16.0)  # must not raise

    assert events == []


def test_piece_arrived_for_an_unknown_piece_id_is_ignored():
    facade, ws = _facade(role='white')
    events = []
    facade.subscribe(events.append)

    ws.queue('piece_arrived', {'piece': _piece_dict(999, 'w', 'R', (7, 0)), 'pos': [4, 0]})
    facade.tick(16.0)  # must not raise

    assert events == []


def test_piece_halted_published_when_arrival_lands_short_of_the_requested_destination():
    """A move blocked mid-flight settles at some cell other than the
    originally requested destination -- the client must surface that as a
    PieceHalted event rather than silently accepting the mismatch."""
    facade, ws = _facade(role='white')
    events = []
    facade.subscribe(events.append)

    ws.queue('move_accepted', {'piece': _piece_dict(3, 'w', 'R', (7, 0)), 'src': [7, 0], 'dest': [4, 0]})
    facade.tick(16.0)
    # Server reports it actually landed at (5, 0), short of the requested (4, 0).
    ws.queue('piece_arrived', {'piece': _piece_dict(3, 'w', 'R', (7, 0)), 'pos': [5, 0]})
    facade.tick(16.0)

    from state.game_events import PieceHalted
    halted = [e for e in events if isinstance(e, PieceHalted)]
    assert len(halted) == 1
    assert halted[0].halted_at == Position(5, 0)
    assert facade.board.piece_at(Position(5, 0)).id == 3


def test_promotion_for_an_unknown_piece_falls_back_to_wire_data():
    """If the promoted piece isn't found on this mirror board (shouldn't
    normally happen, but defensively handled), the event is still published
    using the piece reconstructed straight from the wire payload."""
    facade, ws = _facade(role='white')
    events = []
    facade.subscribe(events.append)

    ws.queue('promotion', {'piece': _piece_dict(999, 'w', 'P', (0, 1)), 'old_kind': 'P', 'new_kind': 'Q'})
    facade.tick(16.0)

    promotions = [e for e in events if isinstance(e, Promotion)]
    assert len(promotions) == 1
    assert promotions[0].piece.id == 999
    # Piece falls back to the wire's own 'piece' payload (still showing the
    # pre-promotion kind) -- new_kind is what carries the promoted kind.
    assert promotions[0].piece.kind is Kind.PAWN
    assert promotions[0].new_kind is Kind.QUEEN
    assert promotions[0].pos == Position(0, 1)


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
