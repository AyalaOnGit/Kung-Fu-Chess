"""
Unit tests for UI/animation/piece_animator.py's PieceAnimator state machine.

Uses a fake SpriteLoader (no real asset files) so tests only exercise the
state machine's own transition/timing logic.
"""
import numpy as np
import pytest

from kungfu_chess.model.piece import Piece, Color, Kind
from kungfu_chess.model.position import Position
from animation.piece_animator import PieceAnimator, PieceAnimatorState
from graphics.sprite_loader import SpriteConfig, SpriteFrame


class _FakeSpriteLoader:
    def __init__(self, animations):
        # animations: {(piece_code, state): (frames, config)}
        self._animations = animations

    def load_frames(self, piece_code, state):
        key = (piece_code, state)
        if key not in self._animations:
            raise FileNotFoundError(key)
        return self._animations[key][0]

    def get_config(self, piece_code, state):
        key = (piece_code, state)
        if key not in self._animations:
            raise FileNotFoundError(key)
        return self._animations[key][1]


def _frame(duration_ms=100.0):
    return SpriteFrame(image=np.zeros((4, 4, 4), dtype=np.uint8), duration_ms=duration_ms)


def _piece():
    return Piece(id=1, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0))


def _animator(animations):
    piece = _piece()
    loader = _FakeSpriteLoader(animations)
    return PieceAnimator(piece=piece, sprite_loader=loader)


def test_piece_code_combines_kind_and_uppercased_color():
    animator = _animator({})
    assert animator._piece_code() == 'RW'


def test_set_state_to_same_state_is_a_no_op():
    animations = {('RW', 'idle'): ([_frame()], SpriteConfig(10.0, True, 'idle'))}
    animator = _animator(animations)
    animator.tick(0)  # loads idle
    frames_before = animator._current_frames

    animator.set_state(PieceAnimatorState.IDLE)

    assert animator._current_frames is frames_before  # not reloaded


def test_set_state_loads_the_new_states_animation():
    animations = {
        ('RW', 'idle'): ([_frame()], SpriteConfig(10.0, True, 'idle')),
        ('RW', 'move'): ([_frame(), _frame()], SpriteConfig(10.0, True, 'idle')),
    }
    animator = _animator(animations)

    animator.set_state(PieceAnimatorState.MOVING)

    assert animator.state == PieceAnimatorState.MOVING
    assert len(animator._current_frames) == 2


def test_tick_advances_frame_index_within_a_looping_animation():
    animations = {
        ('RW', 'idle'): ([_frame(100.0), _frame(100.0)], SpriteConfig(10.0, True, 'idle')),
    }
    animator = _animator(animations)

    animator.tick(50)   # still within frame 0 (0-100ms)
    assert animator.current_frame_index == 0

    animator.tick(60)   # elapsed=110ms -> within frame 1 (100-200ms)
    assert animator.current_frame_index == 1


def test_looping_animation_wraps_elapsed_time_and_returns_none():
    animations = {
        ('RW', 'idle'): ([_frame(100.0), _frame(100.0)], SpriteConfig(10.0, True, 'idle')),
    }
    animator = _animator(animations)

    result = animator.tick(250)  # total duration 200ms, wraps to 50ms

    assert result is None
    assert animator.elapsed_ms == pytest.approx(50.0)


def test_non_looping_animation_transitions_to_next_state_when_finished():
    animations = {
        ('RW', 'move'): ([_frame(100.0)], SpriteConfig(10.0, False, 'short_rest')),
        ('RW', 'short_rest'): ([_frame(100.0)], SpriteConfig(10.0, True, 'short_rest')),
    }
    animator = _animator(animations)
    animator.set_state(PieceAnimatorState.MOVING)

    result = animator.tick(150)  # exceeds the single 100ms frame's duration

    assert result == 'short_rest'
    assert animator.state == PieceAnimatorState.SHORT_REST


def test_missing_animation_falls_back_to_idle():
    animations = {
        ('RW', 'idle'): ([_frame()], SpriteConfig(10.0, True, 'idle')),
    }
    animator = _animator(animations)

    animator.set_state(PieceAnimatorState.JUMPING)  # no ('RW', 'jump') entry

    assert animator._current_frames == animations[('RW', 'idle')][0]


def test_missing_animation_and_missing_idle_falls_back_to_blank_frame():
    animator = _animator({})  # nothing registered, not even idle

    animator.set_state(PieceAnimatorState.JUMPING)

    assert len(animator._current_frames) == 1
    assert animator._current_frames[0].image.shape == (100, 100, 4)


def test_get_current_frame_lazily_loads_if_not_yet_loaded():
    animations = {('RW', 'idle'): ([_frame()], SpriteConfig(10.0, True, 'idle'))}
    animator = _animator(animations)

    frame = animator.get_current_frame()

    assert frame is animations[('RW', 'idle')][0][0]
