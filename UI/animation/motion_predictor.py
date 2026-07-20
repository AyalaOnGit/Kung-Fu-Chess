"""
Pure lerp-based motion prediction.

Interpolates pixel positions during piece movement/jumps using predicted travel times.
"""
from __future__ import annotations
from typing import NamedTuple

from kungfu_chess.config import CELL_SIZE_PX, PIECE_SPEED_PPS
from kungfu_chess.model.position import Position


class PixelMotion(NamedTuple):
    """Represents a piece's motion from one cell to another."""
    src_px: tuple[int, int]  # (x, y) pixel coordinates at start
    dst_px: tuple[int, int]  # (x, y) pixel coordinates at end
    duration_ms: float       # total milliseconds for motion


def cell_distance(src: Position, dst: Position) -> int:
    """Chebyshev distance (in cells) between two board positions."""
    return max(abs(dst.col - src.col), abs(dst.row - src.row))


def duration_for_distance_ms(distance_cells: int) -> float:
    """Milliseconds a slide move covers, given a distance in cells."""
    return distance_cells * (CELL_SIZE_PX * 1000.0 / PIECE_SPEED_PPS)


def duration_for_move_ms(src: Position, dst: Position) -> float:
    """Milliseconds a slide move from src to dst will take."""
    return duration_for_distance_ms(cell_distance(src, dst))


def interpolate_pixel(motion: PixelMotion, elapsed_ms: float) -> tuple[int, int]:
    """
    Linearly interpolate a pixel position along a motion path.
    
    :param motion: PixelMotion describing start, end, and duration
    :param elapsed_ms: milliseconds elapsed since motion started
    :return: (x, y) interpolated pixel position
    """
    if motion.duration_ms <= 0:
        return motion.dst_px
    
    # Clamp t to [0, 1]
    t = min(1.0, elapsed_ms / motion.duration_ms)
    
    src_x, src_y = motion.src_px
    dst_x, dst_y = motion.dst_px
    
    # Linear lerp
    x = src_x + (dst_x - src_x) * t
    y = src_y + (dst_y - src_y) * t
    
    return (int(round(x)), int(round(y)))


def is_motion_complete(motion: PixelMotion, elapsed_ms: float) -> bool:
    """Check if motion has finished."""
    return elapsed_ms >= motion.duration_ms
