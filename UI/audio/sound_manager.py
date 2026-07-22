"""
SoundManager: subscribes to the same GameFacade/NetworkGameFacade event
Subject every other UI component uses (ScorePanel, MovesLogPanel, ...) and
plays a short generated tone for each. Playback is via stdlib `winsound`
(Windows-only, matching this project's environment) so no new dependency is
needed; on any other platform it silently no-ops rather than crashing.
"""
from __future__ import annotations
import pathlib
from typing import Optional

from audio.tone_generator import ensure_tone
from kungfu_chess.model.piece import Color
from state.game_events import GameEvent, GameOver, MoveAccepted, PieceCaptured

try:
    import winsound
    _SOUND_AVAILABLE = True
except ImportError:  # pragma: no cover - non-Windows
    winsound = None
    _SOUND_AVAILABLE = False

_ASSETS_DIR = pathlib.Path(__file__).resolve().parent.parent / 'assets' / 'sounds'

# name -> (chord frequencies Hz, duration ms)
_TONE_SPECS = {
    'move':       ((440.0,), 90),
    'capture':    ((300.0, 500.0), 140),
    'game_start': ((523.25, 659.25, 783.99), 220),
    'game_over':  ((392.0, 493.88), 300),
    'win':        ((523.25, 659.25, 783.99, 1046.50), 350),
    'lose':       ((293.66, 220.00), 350),
}


class SoundManager:
    """
    Call `.on_event(event)` for every GameEvent published by a facade
    (local GameFacade or NetworkGameFacade -- both publish the same
    state.game_events dataclasses), and `.play_start()` once when a game
    screen begins.

    :param my_color: which color the local player is, for win/lose tone
        selection. None (e.g. local hotseat mode, where both colors are
        "mine") plays a neutral game_over tone instead.
    """

    def __init__(self, my_color: Optional[Color] = None, enabled: bool = True):
        self._my_color = my_color
        self._enabled = enabled and _SOUND_AVAILABLE
        self._paths = {}
        if self._enabled:
            for name, (freqs, duration_ms) in _TONE_SPECS.items():
                self._paths[name] = ensure_tone(_ASSETS_DIR / f'{name}.wav', freqs, duration_ms)

    def play_start(self) -> None:
        self._play('game_start')

    def on_event(self, event: GameEvent) -> None:
        if isinstance(event, MoveAccepted):
            self._play('move')
        elif isinstance(event, PieceCaptured):
            self._play('capture')
        elif isinstance(event, GameOver):
            self._play_game_over(event)

    def _play_game_over(self, event: GameOver) -> None:
        if self._my_color is None:
            self._play('game_over')
        elif event.winner is self._my_color:
            self._play('win')
        else:
            self._play('lose')

    def _play(self, name: str) -> None:
        if not self._enabled:
            return
        path = self._paths.get(name)
        if path is None:
            return
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
