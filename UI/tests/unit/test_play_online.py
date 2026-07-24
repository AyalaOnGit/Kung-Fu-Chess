"""
Unit tests for UI/play_online.py's orchestration (login -> lobby -> game
screen), with home_shell/lobby_window/main.py all faked out -- each of
those is already covered by its own test module.
"""
import sys
from types import SimpleNamespace

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


def test_lobby_result_launches_the_network_game():
    ws = _FakeWsClient()
    calls = []

    play_online.main(
        'ws://fake',
        connect_and_login_fn=lambda uri: (ws, 'alice', None),
        run_lobby_fn=lambda ws_client, username: LobbyResult(
            role='white', room_id='room-1', state={'pieces': [], 'game_over': False, 'clock_ms': 0},
            white_username='alice', white_elo=1200, black_username='bob', black_elo=1215,
        ),
        load_game_main_fn=lambda: _fake_game_main(calls),
    )

    assert len(calls) == 1
    assert calls[0]['role'] == 'white'
    assert calls[0]['room_id'] == 'room-1'
    assert ws.closed is True  # closed in the finally block after the game screen returns
    # LobbyResult's rating fields make it all the way to run_network_game.
    assert calls[0]['white_username'] == 'alice' and calls[0]['white_elo'] == 1200
    assert calls[0]['black_username'] == 'bob' and calls[0]['black_elo'] == 1215


def test_resume_envelope_skips_the_lobby_entirely():
    ws = _FakeWsClient()
    resume = Envelope(type='state_sync', data={
        'role': 'black', 'room_id': 'room-2', 'state': {'pieces': [], 'game_over': False, 'clock_ms': 0},
        'white_username': 'alice', 'white_elo': 1200, 'black_username': 'bob', 'black_elo': 1215,
    })

    def _lobby_should_not_be_called(*args, **kwargs):
        raise AssertionError('run_lobby must not be called when resuming a reconnect')

    calls = []
    play_online.main(
        'ws://fake',
        connect_and_login_fn=lambda uri: (ws, 'bob', resume),
        run_lobby_fn=_lobby_should_not_be_called,
        load_game_main_fn=lambda: _fake_game_main(calls),
    )

    assert len(calls) == 1
    assert calls[0]['role'] == 'black'
    assert calls[0]['room_id'] == 'room-2'
    # state_sync's rating fields make it to the HUD on reconnect too.
    assert calls[0]['white_username'] == 'alice' and calls[0]['white_elo'] == 1200
    assert calls[0]['black_username'] == 'bob' and calls[0]['black_elo'] == 1215


def test_resume_envelope_without_rating_fields_falls_back_to_none():
    """Older/degenerate state_sync payloads (e.g. the opponent isn't
    connected to resolve their identity) shouldn't crash -- missing fields
    just fall back to None, same as room_created's empty opponent seat."""
    ws = _FakeWsClient()
    resume = Envelope(type='state_sync', data={
        'role': 'black', 'room_id': 'room-2', 'state': {'pieces': [], 'game_over': False, 'clock_ms': 0},
    })

    calls = []
    play_online.main(
        'ws://fake',
        connect_and_login_fn=lambda uri: (ws, 'bob', resume),
        load_game_main_fn=lambda: _fake_game_main(calls),
    )

    assert calls[0]['white_username'] is None and calls[0]['black_username'] is None


def test_leaving_the_lobby_without_a_result_closes_the_connection_without_starting_a_game():
    ws = _FakeWsClient()
    calls = []

    play_online.main(
        'ws://fake',
        connect_and_login_fn=lambda uri: (ws, 'carol', None),
        run_lobby_fn=lambda ws_client, username: None,
        load_game_main_fn=lambda: _fake_game_main(calls),
    )

    assert calls == []
    assert ws.closed is True


def test_load_game_main_loads_the_real_main_module():
    """Every other test here fakes out _load_game_main entirely, so its
    real implementation (loading UI/main.py by explicit file path, per its
    own docstring's reasoning about sys.path ordering) never runs. Calling
    it for real should produce a usable module exposing exactly what
    play_online.main() needs from it."""
    module = play_online._load_game_main()

    assert hasattr(module, 'Board')
    assert hasattr(module, '_build_mapper')
    assert callable(module.run_network_game)
    assert sys.modules.get('ui_game_main') is module


def test_module_import_inserts_ui_dir_into_sys_path_if_missing():
    """play_online.py's own module-level `if str(ui_dir) not in sys.path:
    sys.path.insert(...)` (mirrors main.py's identical pattern) only
    actually inserts when ui_dir isn't already there -- which it normally
    is by the time any test imports this module. Loads a second, throwaway
    copy of play_online.py by file path with ui_dir removed from sys.path
    first, so its module-level code takes the insert branch for real,
    without disturbing the real 'play_online' module other tests rely on."""
    import importlib.util

    ui_dir_str = str(play_online.ui_dir)
    original_path = list(sys.path)
    try:
        while ui_dir_str in sys.path:
            sys.path.remove(ui_dir_str)
        assert ui_dir_str not in sys.path

        spec = importlib.util.spec_from_file_location(
            'play_online_reload_probe', play_online.ui_dir / 'play_online.py')
        probe_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(probe_module)

        assert ui_dir_str in sys.path
    finally:
        sys.path[:] = original_path
        sys.modules.pop('play_online_reload_probe', None)


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
