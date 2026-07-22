"""
Unit tests for lobby_window.py's LobbyController -- the pure decision logic
behind the Tkinter lobby (Play/Room). No Tkinter window is created here;
_LobbyApp itself is exercised manually since it's a thin GUI shell around
this controller.
"""
import sys
import pathlib

ui_dir = pathlib.Path(__file__).parent.parent.parent
if str(ui_dir) not in sys.path:
    sys.path.insert(0, str(ui_dir))

import server_bridge  # noqa: F401

from lobby_window import LobbyController, LobbyResult
from network.protocol import Envelope


class _FakeWsClient:
    def __init__(self):
        self.sent = []

    def send(self, envelope_type, data=None):
        self.sent.append((envelope_type, data or {}))


def test_play_sends_queue_join():
    ws = _FakeWsClient()
    LobbyController(ws).play()
    assert ws.sent == [('queue_join', {})]


def test_cancel_queue_sends_queue_cancel():
    ws = _FakeWsClient()
    LobbyController(ws).cancel_queue()
    assert ws.sent == [('queue_cancel', {})]


def test_create_room_sends_create_room():
    ws = _FakeWsClient()
    LobbyController(ws).create_room()
    assert ws.sent == [('create_room', {})]


def test_join_room_sends_join_room_with_the_given_id():
    ws = _FakeWsClient()
    LobbyController(ws).join_room('abc123')
    assert ws.sent == [('join_room', {'room_id': 'abc123'})]


def test_match_found_produces_a_finished_outcome():
    controller = LobbyController(_FakeWsClient())
    envelope = Envelope(type='match_found', data={
        'role': 'white', 'room_id': 'room-1', 'state': {'pieces': [], 'game_over': False, 'clock_ms': 0},
    })

    outcome = controller.handle_envelope(envelope)

    assert outcome.finished == LobbyResult(role='white', room_id='room-1',
                                            state={'pieces': [], 'game_over': False, 'clock_ms': 0})
    assert outcome.room_id_display == 'room-1'


def test_room_created_produces_a_finished_outcome():
    controller = LobbyController(_FakeWsClient())
    envelope = Envelope(type='room_created', data={
        'role': 'white', 'room_id': 'room-2', 'state': {'pieces': [], 'game_over': False, 'clock_ms': 0},
    })

    outcome = controller.handle_envelope(envelope)

    assert outcome.finished.room_id == 'room-2'
    assert outcome.finished.role == 'white'


def test_room_joined_produces_a_finished_outcome():
    controller = LobbyController(_FakeWsClient())
    envelope = Envelope(type='room_joined', data={
        'role': 'viewer', 'room_id': 'room-3', 'state': {'pieces': [], 'game_over': False, 'clock_ms': 0},
    })

    outcome = controller.handle_envelope(envelope)

    assert outcome.finished.role == 'viewer'


def test_queue_timeout_error_resets_queue_and_shows_info_popup():
    controller = LobbyController(_FakeWsClient())
    envelope = Envelope(type='error', data={'code': 'queue_timeout'})

    outcome = controller.handle_envelope(envelope)

    assert outcome.finished is None
    assert outcome.queue_reset is True
    assert outcome.info_popup is not None


def test_room_not_found_error_shows_error_popup_without_resetting_queue():
    controller = LobbyController(_FakeWsClient())
    envelope = Envelope(type='error', data={'code': 'room_not_found'})

    outcome = controller.handle_envelope(envelope)

    assert outcome.finished is None
    assert outcome.queue_reset is False
    assert outcome.error_popup == 'No room with that ID.'


def test_already_in_a_room_error_shows_error_popup():
    controller = LobbyController(_FakeWsClient())
    envelope = Envelope(type='error', data={'code': 'already_in_a_room'})

    outcome = controller.handle_envelope(envelope)

    assert outcome.error_popup == 'Already in a room.'


def test_unrelated_envelope_types_produce_an_empty_outcome():
    controller = LobbyController(_FakeWsClient())

    outcome = controller.handle_envelope(Envelope(type='queued', data={}))

    assert outcome == outcome.__class__()  # every field at its default


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
