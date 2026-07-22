"""
Smoke test for UI/main.py's run_local_game() wiring.

Window (and the real cv2 window/mouse-callback it would create) is mocked
out entirely -- is_open() returns False so the render loop body never runs
and no real display window is ever opened. SoundManager.play_start is
mocked too, purely so a headless test run doesn't attempt real audio
playback. Everything else (SpriteLoader, GameFacade, BoardRenderer,
HudRenderer, ui_components) is constructed for real, so this test fails
if run_local_game's wiring is broken (wrong constructor args, missing
import, etc.), which is exactly what a smoke test is for.
"""
from unittest.mock import MagicMock, patch

import main


def test_run_local_game_wires_everything_without_raising():
    fake_window = MagicMock()
    fake_window.is_open.return_value = False  # loop body never executes

    with patch('main.Window', return_value=fake_window), \
         patch('main.SoundManager.play_start', return_value=None):
        main.run_local_game()  # must not raise

    fake_window.set_mouse_callback.assert_called_once()


def _run_network_game_capturing_facade_args(**kwargs):
    """Runs run_network_game with Window/NetworkGameFacade mocked out (no
    real window, no real socket) and returns the kwargs NetworkGameFacade
    was constructed with, so tests can check opponent_present without
    driving the whole render loop."""
    fake_window = MagicMock()
    fake_window.is_open.return_value = False
    fake_facade = MagicMock()

    with patch('main.Window', return_value=fake_window), \
         patch('main.SoundManager.play_start', return_value=None), \
         patch('network.network_game_facade.NetworkGameFacade', return_value=fake_facade) as fake_cls:
        main.run_network_game(
            ws_client=MagicMock(), mapper=MagicMock(), room_id='room1',
            initial_state={'pieces': [], 'game_over': False}, **kwargs,
        )

    return fake_cls.call_args.kwargs


def test_run_network_game_room_creator_starts_with_opponent_absent():
    """my_role='white' with no black_username yet is the room's creator,
    still alone -- NetworkGameFacade must be told the opponent isn't
    present so board interaction stays blocked."""
    kwargs = _run_network_game_capturing_facade_args(
        my_role='white', white_username='alice', black_username=None,
    )
    assert kwargs['opponent_present'] is False


def test_run_network_game_joiner_starts_with_opponent_present():
    """my_role='black' arriving to a room that already has a white player
    -- the opponent (white) is present from the joiner's very first frame."""
    kwargs = _run_network_game_capturing_facade_args(
        my_role='black', white_username='alice', black_username='bob',
    )
    assert kwargs['opponent_present'] is True


def test_run_network_game_viewer_starts_with_opponent_present():
    kwargs = _run_network_game_capturing_facade_args(
        my_role='viewer', white_username='alice', black_username='bob',
    )
    assert kwargs['opponent_present'] is True
