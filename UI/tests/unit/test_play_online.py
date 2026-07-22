"""
Unit tests for UI/play_online.py's orchestration (login -> lobby -> game
screen), with home_shell/lobby_window/main.py all faked out -- each of
those is already covered by its own test module.
"""
import sys
import pathlib
from types import SimpleNamespace

ui_dir = pathlib.Path(__file__).parent.parent.parent
if str(ui_dir) not in sys.path:
    sys.path.insert(0, str(ui_dir))

import server_bridge  # noqa: F401

import play_online
from lobby_window import LobbyResult
from network.protocol import Envelope


class _FakeWsClient:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def _fake_game_main(calls):
    class _FakeBoard:
        def __init__(self, width, height):
            self.width, self.height = width, height

    def fake_build_mapper(board):
        return SimpleNamespace(width=board.width, height=board.height)

    def fake_run_network_game(ws_client, mapper, role, room_id, state,
                               white_username=None, white_elo=None, black_username=None, black_elo=None):
        calls.append({
            'ws_client': ws_client, 'mapper': mapper, 'role': role, 'room_id': room_id, 'state': state,
            'white_username': white_username, 'white_elo': white_elo,
            'black_username': black_username, 'black_elo': black_elo,
        })

    return SimpleNamespace(Board=_FakeBoard, _build_mapper=fake_build_mapper, run_network_game=fake_run_network_game)


def test_lobby_result_launches_the_network_game(monkeypatch):
    ws = _FakeWsClient()
    monkeypatch.setattr(play_online, 'connect_and_login', lambda uri: (ws, 'alice', None))
    monkeypatch.setattr(play_online, 'run_lobby', lambda ws_client, username: LobbyResult(
        role='white', room_id='room-1', state={'pieces': [], 'game_over': False, 'clock_ms': 0},
        white_username='alice', white_elo=1200, black_username='bob', black_elo=1215,
    ))
    calls = []
    monkeypatch.setattr(play_online, '_load_game_main', lambda: _fake_game_main(calls))

    play_online.main('ws://fake')

    assert len(calls) == 1
    assert calls[0]['role'] == 'white'
    assert calls[0]['room_id'] == 'room-1'
    assert ws.closed is True  # closed in the finally block after the game screen returns
    # LobbyResult's rating fields make it all the way to run_network_game.
    assert calls[0]['white_username'] == 'alice' and calls[0]['white_elo'] == 1200
    assert calls[0]['black_username'] == 'bob' and calls[0]['black_elo'] == 1215


def test_resume_envelope_skips_the_lobby_entirely(monkeypatch):
    ws = _FakeWsClient()
    resume = Envelope(type='state_sync', data={
        'role': 'black', 'room_id': 'room-2', 'state': {'pieces': [], 'game_over': False, 'clock_ms': 0},
        'white_username': 'alice', 'white_elo': 1200, 'black_username': 'bob', 'black_elo': 1215,
    })
    monkeypatch.setattr(play_online, 'connect_and_login', lambda uri: (ws, 'bob', resume))

    def _lobby_should_not_be_called(*args, **kwargs):
        raise AssertionError('run_lobby must not be called when resuming a reconnect')
    monkeypatch.setattr(play_online, 'run_lobby', _lobby_should_not_be_called)

    calls = []
    monkeypatch.setattr(play_online, '_load_game_main', lambda: _fake_game_main(calls))

    play_online.main('ws://fake')

    assert len(calls) == 1
    assert calls[0]['role'] == 'black'
    assert calls[0]['room_id'] == 'room-2'
    # state_sync's rating fields make it to the HUD on reconnect too.
    assert calls[0]['white_username'] == 'alice' and calls[0]['white_elo'] == 1200
    assert calls[0]['black_username'] == 'bob' and calls[0]['black_elo'] == 1215


def test_resume_envelope_without_rating_fields_falls_back_to_none(monkeypatch):
    """Older/degenerate state_sync payloads (e.g. the opponent isn't
    connected to resolve their identity) shouldn't crash -- missing fields
    just fall back to None, same as room_created's empty opponent seat."""
    ws = _FakeWsClient()
    resume = Envelope(type='state_sync', data={
        'role': 'black', 'room_id': 'room-2', 'state': {'pieces': [], 'game_over': False, 'clock_ms': 0},
    })
    monkeypatch.setattr(play_online, 'connect_and_login', lambda uri: (ws, 'bob', resume))

    calls = []
    monkeypatch.setattr(play_online, '_load_game_main', lambda: _fake_game_main(calls))

    play_online.main('ws://fake')

    assert calls[0]['white_username'] is None and calls[0]['black_username'] is None


def test_leaving_the_lobby_without_a_result_closes_the_connection_without_starting_a_game(monkeypatch):
    ws = _FakeWsClient()
    monkeypatch.setattr(play_online, 'connect_and_login', lambda uri: (ws, 'carol', None))
    monkeypatch.setattr(play_online, 'run_lobby', lambda ws_client, username: None)

    calls = []
    monkeypatch.setattr(play_online, '_load_game_main', lambda: _fake_game_main(calls))

    play_online.main('ws://fake')

    assert calls == []
    assert ws.closed is True


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
