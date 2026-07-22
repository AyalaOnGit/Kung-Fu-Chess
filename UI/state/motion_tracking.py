"""
Shared pending-motion tracking for GameFacade and NetworkGameFacade.

Both predict in-flight animation the same way (same kungfu_chess.config
constants), just from different clocks -- GameFacade's local GameEngine
vs NetworkGameFacade's client-side tick accumulator -- and previously
each defined its own copy of PendingMotionData plus the pixel-motion
computation in get_pending_motion. Extracted here so there's one
definition instead of two kept in sync by convention.
"""
from __future__ import annotations
from dataclasses import dataclass

from kungfu_chess.config import JUMP_DURATION_MS
from kungfu_chess.interaction.board_mapper import BoardMapper
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position

from animation.motion_predictor import PixelMotion, duration_for_move_ms


@dataclass
class PendingMotionData:
    """Tracks a piece in motion."""
    piece: Piece
    src_pos: Position
    dst_pos: Position
    is_jump: bool
    motion_start_time_ms: float  # clock_ms when motion began
    motion_end_time_ms: float    # clock_ms when motion will finish


def pixel_motion_for(motion_data: PendingMotionData, mapper: BoardMapper,
                      now_ms: float) -> tuple[PixelMotion, float]:
    """Return (PixelMotion, elapsed_ms) for a pending motion as of now_ms."""
    elapsed_ms = now_ms - motion_data.motion_start_time_ms
    src_px = mapper.cell_center_pixel(motion_data.src_pos)
    dst_px = mapper.cell_center_pixel(motion_data.dst_pos)
    duration_ms = float(JUMP_DURATION_MS) if motion_data.is_jump \
        else duration_for_move_ms(motion_data.src_pos, motion_data.dst_pos)
    return PixelMotion(src_px=src_px, dst_px=dst_px, duration_ms=duration_ms), elapsed_ms
