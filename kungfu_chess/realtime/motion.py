from __future__ import annotations
from dataclasses import dataclass
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece
from kungfu_chess.config import CELL_SIZE_PX, PIECE_SPEED_PPS, JUMP_DURATION_MS


def travel_duration_ms(src: Position, dest: Position) -> int:
    """
    Return travel time in milliseconds based on cell-step count.

    Uses Chebyshev distance (max of row/col steps) so diagonal moves
    cost the same per step as straight moves.
    """
    steps = max(abs(dest.row - src.row), abs(dest.col - src.col))
    return steps * (CELL_SIZE_PX * 1000 // PIECE_SPEED_PPS)


@dataclass
class Motion:
    """
    Represents a piece in transit from src to dest.

    The piece remains logically on src until arrival_time is reached.
    """
    piece:        Piece
    src:          Position
    dest:         Position
    arrival_time: int   # absolute clock ms


@dataclass
class JumpMotion:
    """
    Represents a piece that is airborne (jumping).

    The piece remains logically on its cell for the duration of the jump.
    An enemy piece arriving at cell during [start_time, landing_time] is captured.
    """
    piece:        Piece
    cell:         Position
    landing_time: int   # absolute clock ms
