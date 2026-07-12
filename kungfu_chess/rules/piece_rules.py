from __future__ import annotations
from abc import ABC, abstractmethod
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece, Kind, Color
from kungfu_chess.model.board import Board


class PieceRule(ABC):
    """
    Abstract base for per-piece movement rules.

    Stateless: no selected pieces, no timing, no game-over state.
    """

    @abstractmethod
    def legal_destinations(self, board: Board, piece: Piece) -> set[Position]:
        """
        Return all positions this piece may legally move to from its current cell.

        Enemy-occupied destinations are included (capture).
        Friendly-occupied destinations are excluded.
        Does not mutate the board.
        """


class _SlidingRule(PieceRule):
    """Shared sliding logic for rook, bishop, and queen."""

    def __init__(self, directions: list[tuple[int, int]]):
        self._directions = directions

    def legal_destinations(self, board: Board, piece: Piece) -> set[Position]:
        result = set()
        for dr, dc in self._directions:
            r, c = piece.cell.row + dr, piece.cell.col + dc
            while True:
                pos = Position(r, c)
                if not board.in_bounds(pos):
                    break
                occupant = board.piece_at(pos)
                if occupant is None:
                    result.add(pos)
                elif occupant.color != piece.color:
                    result.add(pos)
                    break
                else:
                    break
                r += dr
                c += dc
        return result


class RookRule(_SlidingRule):
    """Horizontal and vertical sliding until blocked."""

    def __init__(self):
        super().__init__([(0, 1), (0, -1), (1, 0), (-1, 0)])


class BishopRule(_SlidingRule):
    """Diagonal sliding until blocked."""

    def __init__(self):
        super().__init__([(1, 1), (1, -1), (-1, 1), (-1, -1)])


class QueenRule(PieceRule):
    """Rook movement plus bishop movement."""

    def __init__(self):
        self._rook   = RookRule()
        self._bishop = BishopRule()

    def legal_destinations(self, board: Board, piece: Piece) -> set[Position]:
        return self._rook.legal_destinations(board, piece) | \
               self._bishop.legal_destinations(board, piece)


class KnightRule(PieceRule):
    """L-shaped jumps, ignoring blockers."""

    _OFFSETS = [(2, 1), (2, -1), (-2, 1), (-2, -1),
                (1, 2), (1, -2), (-1, 2), (-1, -2)]

    def legal_destinations(self, board: Board, piece: Piece) -> set[Position]:
        result = set()
        for dr, dc in self._OFFSETS:
            pos = Position(piece.cell.row + dr, piece.cell.col + dc)
            if not board.in_bounds(pos):
                continue
            occupant = board.piece_at(pos)
            if occupant is None or occupant.color != piece.color:
                result.add(pos)
        return result


class KingRule(PieceRule):
    """One square in any direction."""

    _OFFSETS = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                if (dr, dc) != (0, 0)]

    def legal_destinations(self, board: Board, piece: Piece) -> set[Position]:
        result = set()
        for dr, dc in self._OFFSETS:
            pos = Position(piece.cell.row + dr, piece.cell.col + dc)
            if not board.in_bounds(pos):
                continue
            occupant = board.piece_at(pos)
            if occupant is None or occupant.color != piece.color:
                result.add(pos)
        return result


class PawnRule(PieceRule):
    """
    Pawn movement:
      - Moves one step forward (white = up, black = down).
      - Captures one diagonal step forward.
      - May move two steps forward from the starting row if both squares are clear.
      - No en passant, no promotion.
    """

    def legal_destinations(self, board: Board, piece: Piece) -> set[Position]:
        result = set()
        direction = -1 if piece.color is Color.WHITE else 1
        start_row = self._start_row(piece.color, board.height)
        r, c = piece.cell.row, piece.cell.col

        # One step forward
        one_step = Position(r + direction, c)
        if board.in_bounds(one_step) and board.is_empty(one_step):
            result.add(one_step)
            # Two steps forward from starting row
            two_step = Position(r + 2 * direction, c)
            if r == start_row and board.in_bounds(two_step) and board.is_empty(two_step):
                result.add(two_step)

        # Diagonal captures
        for dc in (-1, 1):
            diag = Position(r + direction, c + dc)
            if not board.in_bounds(diag):
                continue
            occupant = board.piece_at(diag)
            if occupant is not None and occupant.color != piece.color:
                result.add(diag)

        return result

    @staticmethod
    def _start_row(color: Color, height: int) -> int:
        """Return the starting row for double-move. White starts on row height-2, black on row 1."""
        return height - 2 if color is Color.WHITE else 1


# --- Registry ---

PIECE_RULES: dict[Kind, PieceRule] = {
    Kind.ROOK:   RookRule(),
    Kind.BISHOP: BishopRule(),
    Kind.QUEEN:  QueenRule(),
    Kind.KNIGHT: KnightRule(),
    Kind.KING:   KingRule(),
    Kind.PAWN:   PawnRule(),
}


def get_rule(kind: Kind) -> PieceRule:
    """Return the PieceRule for the given Kind."""
    return PIECE_RULES[kind]
