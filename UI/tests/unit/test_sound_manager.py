"""
Unit tests for UI/audio/tone_generator.py and UI/audio/sound_manager.py.
"""
import sys
import pathlib
import wave

ui_dir = pathlib.Path(__file__).parent.parent.parent
if str(ui_dir) not in sys.path:
    sys.path.insert(0, str(ui_dir))

import path_bootstrap  # noqa: F401

from audio.tone_generator import ensure_tone, generate_tone
from audio.sound_manager import SoundManager, _TONE_SPECS
from kungfu_chess.model.piece import Color, Kind, Piece
from kungfu_chess.model.position import Position
from state.game_events import GameOver, MoveAccepted, PieceCaptured


def test_generate_tone_writes_a_valid_mono_16bit_wav(tmp_path):
    path = tmp_path / 'blip.wav'
    generate_tone(path, frequencies_hz=(440.0,), duration_ms=100)

    assert path.exists()
    with wave.open(str(path), 'rb') as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getnframes() > 0


def test_ensure_tone_does_not_regenerate_an_existing_file(tmp_path):
    path = tmp_path / 'blip.wav'
    ensure_tone(path, frequencies_hz=(440.0,), duration_ms=100)
    first_mtime = path.stat().st_mtime_ns

    ensure_tone(path, frequencies_hz=(440.0,), duration_ms=100)

    assert path.stat().st_mtime_ns == first_mtime


def test_sound_manager_disabled_never_touches_winsound():
    # enabled=False must be a full no-op regardless of platform/audio state.
    manager = SoundManager(my_color=Color.WHITE, enabled=False)
    piece = Piece(id=1, color=Color.WHITE, kind=Kind.PAWN, cell=Position(4, 4))

    manager.play_start()
    manager.on_event(MoveAccepted(piece=piece, src_pos=Position(6, 4), dst_pos=Position(4, 4)))
    manager.on_event(PieceCaptured(piece=piece, capturer=piece, pos=Position(4, 4)))
    manager.on_event(GameOver(winner=Color.WHITE, loser=Color.BLACK))
    # No exception is the assertion: a disabled manager must be silent no matter what it's fed.


def test_sound_manager_picks_win_or_lose_tone_by_local_color(monkeypatch, tmp_path):
    import audio.sound_manager as sound_manager_module
    monkeypatch.setattr(sound_manager_module, '_ASSETS_DIR', tmp_path)

    played = []
    manager = SoundManager(my_color=Color.WHITE, enabled=True)
    monkeypatch.setattr(manager, '_play', played.append)

    manager.on_event(GameOver(winner=Color.WHITE, loser=Color.BLACK))
    assert played == ['win']

    played.clear()
    manager.on_event(GameOver(winner=Color.BLACK, loser=Color.WHITE))
    assert played == ['lose']


def test_sound_manager_plays_neutral_game_over_when_no_local_color(monkeypatch, tmp_path):
    import audio.sound_manager as sound_manager_module
    monkeypatch.setattr(sound_manager_module, '_ASSETS_DIR', tmp_path)

    played = []
    manager = SoundManager(my_color=None, enabled=True)
    monkeypatch.setattr(manager, '_play', played.append)

    manager.on_event(GameOver(winner=Color.WHITE, loser=Color.BLACK))
    assert played == ['game_over']


def test_tone_specs_cover_every_event_the_manager_handles():
    assert {'move', 'capture', 'game_start', 'game_over', 'win', 'lose'} == set(_TONE_SPECS)


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
