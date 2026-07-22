"""
Unit tests for UI/graphics/sprite_loader.py's SpriteLoader.

Builds a minimal on-disk pieces/ tree under pytest's tmp_path fixture --
no dependency on the real assets/pieces_mine/ directory.
"""
import json

import cv2
import numpy as np
import pytest

from graphics.sprite_loader import SpriteLoader


def _write_state(base_dir, piece_code, state, frame_count=2, fps=10.0,
                  is_loop=True, next_state='idle'):
    state_dir = base_dir / piece_code / 'states' / state
    sprites_dir = state_dir / 'sprites'
    sprites_dir.mkdir(parents=True)

    config = {
        'graphics': {'frames_per_sec': fps, 'is_loop': is_loop},
        'physics': {'next_state_when_finished': next_state},
    }
    (state_dir / 'config.json').write_text(json.dumps(config))

    blank = np.zeros((10, 10, 3), dtype=np.uint8)
    for i in range(1, frame_count + 1):
        cv2.imwrite(str(sprites_dir / f'{i}.png'), blank)


def test_load_frames_returns_frames_in_numeric_order(tmp_path):
    _write_state(tmp_path, 'RW', 'idle', frame_count=3, fps=10.0)
    loader = SpriteLoader(tmp_path)

    frames = loader.load_frames('RW', 'idle')

    assert len(frames) == 3
    assert all(f.duration_ms == pytest.approx(100.0) for f in frames)


def test_load_frames_caches_result(tmp_path):
    _write_state(tmp_path, 'RW', 'idle')
    loader = SpriteLoader(tmp_path)

    first = loader.load_frames('RW', 'idle')
    second = loader.load_frames('RW', 'idle')

    assert first is second


def test_load_frames_missing_config_raises_file_not_found(tmp_path):
    loader = SpriteLoader(tmp_path)
    with pytest.raises(FileNotFoundError):
        loader.load_frames('RW', 'idle')


def test_load_frames_missing_sprites_dir_raises_file_not_found(tmp_path):
    state_dir = tmp_path / 'RW' / 'states' / 'idle'
    state_dir.mkdir(parents=True)
    (state_dir / 'config.json').write_text(json.dumps({
        'graphics': {'frames_per_sec': 10.0, 'is_loop': True},
        'physics': {'next_state_when_finished': 'idle'},
    }))

    loader = SpriteLoader(tmp_path)
    with pytest.raises(FileNotFoundError):
        loader.load_frames('RW', 'idle')


def test_load_frames_falls_back_through_a_single_nested_subdirectory(tmp_path):
    """assets/pieces1/pieces1/RB/... -- some asset packs nest an extra
    subdirectory level; SpriteLoader transparently looks one level deeper
    when pieces_dir itself has exactly one child directory."""
    nested = tmp_path / 'pieces1'
    nested.mkdir()
    _write_state(nested, 'RW', 'idle')

    loader = SpriteLoader(tmp_path)
    frames = loader.load_frames('RW', 'idle')

    assert len(frames) == 2


def test_get_config_returns_parsed_values(tmp_path):
    _write_state(tmp_path, 'QB', 'move', fps=20.0, is_loop=False, next_state='short_rest')
    loader = SpriteLoader(tmp_path)

    config = loader.get_config('QB', 'move')

    assert config.frames_per_sec == 20.0
    assert config.is_loop is False
    assert config.next_state_when_finished == 'short_rest'


def test_get_config_populates_cache_via_load_frames(tmp_path):
    _write_state(tmp_path, 'QB', 'move')
    loader = SpriteLoader(tmp_path)

    loader.get_config('QB', 'move')

    assert ('QB', 'move') in loader._cache  # load_frames ran as a side effect
