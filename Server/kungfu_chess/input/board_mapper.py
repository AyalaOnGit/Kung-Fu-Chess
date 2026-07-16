from __future__ import annotations
from kungfu_chess.model.position import Position
from kungfu_chess.config import CELL_SIZE_PX


class BoardMapper:
    """
    Coordinate Adapter: converts pixel coordinates to board Positions.

    Supports two modes:
      1. Exact boundaries (col_boundaries, row_boundaries) — pixel-perfect mapping
         when the board image has non-uniform cell sizes or a border offset.
      2. Uniform offset (offset_x, offset_y) — simple fallback using CELL_SIZE_PX.
    """

    def __init__(self, width: int, height: int,
                 offset_x: int = 0, offset_y: int = 0,
                 col_boundaries: list[int] | None = None,
                 row_boundaries: list[int] | None = None):
        self._width    = width
        self._height   = height
        self._offset_x = offset_x
        self._offset_y = offset_y
        # Exact boundaries (len = n_cols+1 and n_rows+1)
        self._cols = col_boundaries  # e.g. [2, 104, 206, ...]
        self._rows = row_boundaries  # e.g. [6, 108, 211, ...]

    def pixel_to_position(self, x: int, y: int) -> Position:
        """Convert pixel (x, y) to a board Position."""
        if self._cols and self._rows:
            col = self._boundary_index(x, self._cols)
            row = self._boundary_index(y, self._rows)
        else:
            col = (x - self._offset_x) // CELL_SIZE_PX
            row = (y - self._offset_y) // CELL_SIZE_PX
        return Position(row=row, col=col)

    def position_to_pixel(self, pos: Position) -> tuple[int, int]:
        """Return the top-left pixel of a board cell."""
        if self._cols and self._rows:
            x = self._cols[pos.col]
            y = self._rows[pos.row]
        else:
            x = pos.col * CELL_SIZE_PX + self._offset_x
            y = pos.row * CELL_SIZE_PX + self._offset_y
        return x, y

    def cell_center_pixel(self, pos: Position) -> tuple[int, int]:
        """Return the center pixel of a board cell."""
        if self._cols and self._rows:
            x = (self._cols[pos.col] + self._cols[pos.col + 1]) // 2
            y = (self._rows[pos.row] + self._rows[pos.row + 1]) // 2
        else:
            x = pos.col * CELL_SIZE_PX + self._offset_x + CELL_SIZE_PX // 2
            y = pos.row * CELL_SIZE_PX + self._offset_y + CELL_SIZE_PX // 2
        return x, y

    def cell_size(self, pos: Position) -> tuple[int, int]:
        """Return (width, height) of a specific cell in pixels."""
        if self._cols and self._rows:
            cw = self._cols[pos.col + 1] - self._cols[pos.col]
            ch = self._rows[pos.row + 1] - self._rows[pos.row]
            return cw, ch
        return CELL_SIZE_PX, CELL_SIZE_PX

    def in_bounds_px(self, x: int, y: int) -> bool:
        """Return True if the pixel coordinate maps to a valid board cell."""
        if self._cols and self._rows:
            return (self._cols[0] <= x < self._cols[-1] and
                    self._rows[0] <= y < self._rows[-1])
        pos = self.pixel_to_position(x, y)
        return 0 <= pos.row < self._height and 0 <= pos.col < self._width

    @staticmethod
    def _boundary_index(px: int, boundaries: list[int]) -> int:
        """Return which cell index px falls into given boundary list."""
        for i in range(len(boundaries) - 1):
            if boundaries[i] <= px < boundaries[i + 1]:
                return i
        # Clamp to last cell
        return len(boundaries) - 2
