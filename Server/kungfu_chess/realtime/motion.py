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
class CooldownTimer:
    """
    Represents a piece that is cooling down after arriving at its destination.

    The piece cannot be moved again until ready_time is reached.
    """
    piece:      Piece
    ready_time: int   # absolute clock ms when cooldown expires


def compute_path(src: Position, dest: Position) -> list[Position]:
    """
    Return every cell strictly between src and dest along the rectilinear or
    diagonal ray, not including src itself but including dest.

    For knights (non-ray moves) returns [dest] only — no intermediate cells.
    """
    dr = dest.row - src.row
    dc = dest.col - src.col
    steps = max(abs(dr), abs(dc))
    if steps == 0:
        return []
    # Pure horizontal, vertical, or 45-degree diagonal → ray move
    if dr == 0 or dc == 0 or abs(dr) == abs(dc):
        step_r = dr // steps
        step_c = dc // steps
        return [
            Position(src.row + step_r * i, src.col + step_c * i)
            for i in range(1, steps + 1)
        ]
    # Knight or other non-ray move — no intermediate cells
    return [dest]


@dataclass
class Motion:
    """
    Represents a piece in transit from src to dest.

    The piece remains logically on src until arrival_time is reached.
    path holds every cell from the step after src up to and including dest,
    used for dynamic path-blocking checks during travel.
    start_time_ms is set once on creation so current_step stays accurate
    even after redirect_motion shortens the path.
    """
    piece:          Piece
    src:            Position
    dest:           Position
    arrival_time:   int             # absolute clock ms (updated on redirect)
    path:           list[Position] = None
    start_time_ms:  int = None      # set once in __post_init__, never changed

    def __post_init__(self):
        if self.path is None:
            self.path = compute_path(self.src, self.dest)
        if self.start_time_ms is None:
            self.start_time_ms = self.arrival_time - travel_duration_ms(self.src, self.dest)

    def current_step(self, clock_ms: int) -> int:
        """
        Return the 0-based index into the current path of the cell the piece
        is heading toward right now.

        Uses original start_time so progress is never skewed by redirects.
        Each path cell represents one cell-step; we compute how many steps
        have elapsed out of the current path length.
        """
        if not self.path:
            return 0
        from kungfu_chess.config import CELL_SIZE_PX, PIECE_SPEED_PPS
        ms_per_step = CELL_SIZE_PX * 1000 // PIECE_SPEED_PPS
        elapsed_steps = (clock_ms - self.start_time_ms) / ms_per_step
        idx = int(elapsed_steps)
        return max(0, min(idx, len(self.path) - 1))


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
