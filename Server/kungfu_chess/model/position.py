from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    """
    Immutable value object representing a board cell by row and column.

    Does not know board size, pixels, movement rules, or rendering.
    """
    row: int
    col: int

    def __repr__(self):
        return f"Position(row={self.row}, col={self.col})"
