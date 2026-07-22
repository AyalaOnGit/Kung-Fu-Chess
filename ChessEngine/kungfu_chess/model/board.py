from __future__ import annotations
from typing import Optional
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece


class BoardError(Exception):
    """Raised when a Board operation violates occupancy rules."""


class Board:
    """
    Owns the logical arrangement of pieces on the grid.

    Responsibilities:
      - Store width and height.
      - Add, remove, and query pieces by cell.
      - Check cell bounds.
      - Move a piece after validation has already happened elsewhere.

    Board does not contain chess movement rules.
    Board.move_piece assumes the caller has validated the move.
    """

    def __init__(self, width: int, height: int):
        self.width  = width
        self.height = height
        self._grid: dict[Position, Piece] = {}

    # --- Bounds ---

    def in_bounds(self, pos: Position) -> bool:
        """Return True if pos is within the board dimensions."""
        return 0 <= pos.row < self.height and 0 <= pos.col < self.width

    # --- Piece access ---

    def piece_at(self, pos: Position) -> Optional[Piece]:
        """Return the piece at pos, or None if the cell is empty."""
        return self._grid.get(pos)

    def is_empty(self, pos: Position) -> bool:
        """Return True if pos contains no piece."""
        return pos not in self._grid

    def all_pieces(self) -> list[Piece]:
        """Return all pieces currently on the board."""
        return list(self._grid.values())

    # --- Mutation (called only after external validation) ---

    def add_piece(self, piece: Piece) -> None:
        """
        Place piece on the board at piece.cell.

        :raises BoardError: if the cell is already occupied.
        """
        if not self.is_empty(piece.cell):
            raise BoardError(f"Cell {piece.cell} is already occupied.")
        self._grid[piece.cell] = piece

    def remove_piece(self, pos: Position) -> None:
        """
        Remove the piece at pos and mark it as CAPTURED.

        :raises BoardError: if the cell is empty.
        """
        piece = self._grid.pop(pos, None)
        if piece is None:
            raise BoardError(f"No piece at {pos} to remove.")
        piece.mark_captured()

    def move_piece(self, src: Position, dest: Position) -> None:
        """
        Move the piece at src to dest.

        Captures any enemy piece already at dest.
        Assumes the move has been validated by RuleEngine.

        :raises BoardError: if src is empty.
        """
        piece = self._grid.pop(src, None)
        if piece is None:
            raise BoardError(f"No piece at {src} to move.")
        existing = self._grid.get(dest)
        if existing is not None:
            existing.mark_captured()
        piece.cell = dest
        self._grid[dest] = piece
