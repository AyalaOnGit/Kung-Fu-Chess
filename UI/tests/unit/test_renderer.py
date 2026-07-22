"""
Unit tests for UI/graphics/renderer.py's BoardRenderer.

Uses a temp sprite tree (like test_sprite_loader.py) and a fake facade
duck-typing GameFacade's get_pending_motion/get_cooldown_ratio, so these
tests never touch real assets or open a real display window.
"""
import json

import cv2
import numpy as np

from kungfu_chess.interaction.board_mapper import BoardMapper
from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece, Color, Kind, PieceState
from kungfu_chess.model.position import Position

from animation.motion_predictor import PixelMotion
from animation.piece_animator import PieceAnimatorState
from graphics.renderer import BoardRenderer
from graphics.sprite_loader import SpriteLoader

CELL_PX = 100


def _write_sprite_state(base_dir, piece_code, state, fps=10.0, is_loop=True, next_state='idle'):
    state_dir = base_dir / piece_code / 'states' / state
    sprites_dir = state_dir / 'sprites'
    sprites_dir.mkdir(parents=True)
    config = {
        'graphics': {'frames_per_sec': fps, 'is_loop': is_loop},
        'physics': {'next_state_when_finished': next_state},
    }
    (state_dir / 'config.json').write_text(json.dumps(config))
    blank = np.zeros((20, 20, 4), dtype=np.uint8)
    blank[:, :, 3] = 255
    cv2.imwrite(str(sprites_dir / '1.png'), blank)


def _all_states(base_dir, piece_code):
    for state in ('idle', 'move', 'jump', 'short_rest'):
        _write_sprite_state(base_dir, piece_code, state)


class _FakeFacade:
    def __init__(self, pending=None, cooldown_ratio=0.0):
        self._pending = pending or {}
        self._cooldown_ratio = cooldown_ratio

    def get_pending_motion(self, piece_id):
        return self._pending.get(piece_id)

    def get_cooldown_ratio(self, piece):
        return self._cooldown_ratio


def _renderer(board, sprites_dir, facade=None):
    mapper = BoardMapper(board.width, board.height)
    loader = SpriteLoader(sprites_dir)
    facade = facade if facade is not None else _FakeFacade()
    # Nonexistent board image path -> BoardRenderer falls back to a
    # deterministically-sized generated blank board, no real asset needed.
    return BoardRenderer(board, loader, str(sprites_dir / 'no-such-board.png'), facade, mapper)


def test_render_returns_image_sized_to_the_board(tmp_path):
    board = Board(width=8, height=8)
    renderer = _renderer(board, tmp_path)

    frame = renderer.render(dt_ms=16.0)

    assert frame.shape == (8 * CELL_PX, 8 * CELL_PX, 4)


def test_render_with_a_static_piece_does_not_raise(tmp_path):
    _all_states(tmp_path, 'RW')
    board = Board(width=8, height=8)
    board.add_piece(Piece(id=1, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0)))
    renderer = _renderer(board, tmp_path)

    frame = renderer.render(dt_ms=16.0)

    assert frame is not None


def test_render_with_a_piece_in_flight_does_not_raise(tmp_path):
    _all_states(tmp_path, 'RW')
    board = Board(width=8, height=8)
    piece = Piece(id=1, color=Color.WHITE, kind=Kind.MOVING if False else Kind.ROOK,
                  cell=Position(0, 3), state=PieceState.MOVING)
    board.add_piece(piece)
    pending = {1: (PixelMotion(src_px=(50, 50), dst_px=(350, 50), duration_ms=3000.0), 1000.0)}
    renderer = _renderer(board, tmp_path, facade=_FakeFacade(pending=pending))

    frame = renderer.render(dt_ms=16.0)

    assert frame is not None


def test_render_with_a_cooling_piece_draws_cooldown_bar_without_raising(tmp_path):
    _all_states(tmp_path, 'RW')
    board = Board(width=8, height=8)
    piece = Piece(id=1, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0),
                  state=PieceState.COOLING)
    board.add_piece(piece)
    renderer = _renderer(board, tmp_path, facade=_FakeFacade(cooldown_ratio=0.5))

    frame = renderer.render(dt_ms=16.0)

    assert frame is not None


def test_render_with_selection_and_halted_piece_does_not_raise(tmp_path):
    _all_states(tmp_path, 'RW')
    board = Board(width=8, height=8)
    piece = Piece(id=1, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0))
    board.add_piece(piece)
    renderer = _renderer(board, tmp_path)

    renderer.set_selection(Position(0, 0))
    renderer.set_halted_piece(1)
    frame = renderer.render(dt_ms=16.0)

    assert frame is not None


def test_render_with_a_jumping_piece_does_not_raise(tmp_path):
    _all_states(tmp_path, 'RW')
    board = Board(width=8, height=8)
    piece = Piece(id=1, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0),
                  state=PieceState.JUMPING)
    board.add_piece(piece)
    renderer = _renderer(board, tmp_path)

    frame = renderer.render(dt_ms=16.0)

    assert frame is not None


def test_one_shot_animation_does_not_restart_after_naturally_finishing(tmp_path):
    """Regression test: a non-looping animation (jump, short_rest) that
    finishes its own sprite frames and auto-transitions to its resting
    pose must not get forced back into the original state by the next
    render() call just because piece.state hasn't changed yet -- only an
    actual change in piece.state should retrigger it. Comparing against
    animator.state (which drifts once it self-transitions) instead of
    what render() itself last drove it to caused the animation to restart
    from frame 0 repeatedly, for as long as piece.state stayed the same --
    this is what made jumps look like they never finished."""
    _write_sprite_state(tmp_path, 'RW', 'jump', fps=10.0, is_loop=False, next_state='idle')
    _write_sprite_state(tmp_path, 'RW', 'idle', fps=10.0, is_loop=True, next_state='idle')
    board = Board(width=8, height=8)
    piece = Piece(id=1, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0), state=PieceState.JUMPING)
    board.add_piece(piece)
    renderer = _renderer(board, tmp_path)

    renderer.render(dt_ms=16.0)  # first frame: animator driven into JUMPING
    animator = renderer._animators[1]
    assert animator.state == PieceAnimatorState.JUMPING

    renderer.render(dt_ms=200.0)  # single 100ms frame's worth -> auto-transitions to idle
    assert animator.state == PieceAnimatorState.IDLE

    renderer.render(dt_ms=16.0)  # piece.state is STILL JUMPING -- must not restart
    assert animator.state == PieceAnimatorState.IDLE


def test_missing_sprites_falls_back_gracefully_without_raising(tmp_path):
    """No sprite assets registered at all for this piece code -- _draw_piece
    catches its own exceptions and just skips drawing that piece."""
    board = Board(width=8, height=8)
    board.add_piece(Piece(id=1, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 0)))
    renderer = _renderer(board, tmp_path)

    frame = renderer.render(dt_ms=16.0)

    assert frame is not None
