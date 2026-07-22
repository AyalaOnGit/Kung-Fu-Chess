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
