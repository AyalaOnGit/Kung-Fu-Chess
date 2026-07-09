from __future__ import annotations
from kungfu_chess.model.position import Position
from kungfu_chess.config import CELL_SIZE_PX


class BoardMapper:
    """
    Coordinate Adapter: converts pixel coordinates to board Positions.

    Does not know chess rules, game state, or rendering.
    """

    def __init__(self, width: int, height: int):
        self._width  = width
        self._height = height

    def pixel_to_position(self, x: int, y: int) -> Position:
        """
        Convert pixel (x, y) to a board Position.

        :return: Position(row, col) for the cell containing the pixel.
        """
        return Position(row=y // CELL_SIZE_PX, col=x // CELL_SIZE_PX)

    def in_bounds_px(self, x: int, y: int) -> bool:
        """Return True if the pixel coordinate maps to a valid board cell."""
        pos = self.pixel_to_position(x, y)
        return 0 <= pos.row < self._height and 0 <= pos.col < self._width
