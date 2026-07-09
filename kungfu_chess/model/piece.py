from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from kungfu_chess.model.position import Position


class Color(Enum):
    """The two player colors."""
    WHITE = 'w'
    BLACK = 'b'

    def opponent(self):
        """Return the opposing color."""
        return Color.BLACK if self is Color.WHITE else Color.WHITE


class Kind(Enum):
    """All supported piece types."""
    KING   = 'K'
    QUEEN  = 'Q'
    ROOK   = 'R'
    BISHOP = 'B'
    KNIGHT = 'N'
    PAWN   = 'P'


class PieceState(Enum):
    """Lifecycle state of a piece on the board."""
    IDLE     = 'idle'
    MOVING   = 'moving'
    JUMPING  = 'jumping'
    CAPTURED = 'captured'


@dataclass
class Piece:
    """
    Represents a single chess piece.

    id     — stable identity used for motion tracking and snapshots.
    color  — WHITE or BLACK.
    kind   — piece type (KING, QUEEN, …).
    cell   — current logical board position (source cell while moving).
    state  — lifecycle flag: IDLE, MOVING, JUMPING, or CAPTURED.

    A Piece does not know about pixels, rendering, movement rules, or input.
    """
    id:    int
    color: Color
    kind:  Kind
    cell:  Position
    state: PieceState = field(default=PieceState.IDLE)

    def token(self) -> str:
        """Return the canonical two-character display token, e.g. 'wR'."""
        return self.color.value + self.kind.value

    @staticmethod
    def is_royal(kind: Kind) -> bool:
        """Return True if capturing this kind ends the game."""
        return kind is Kind.KING

    @staticmethod
    def promotion_kind(kind: Kind) -> Kind:
        """
        Return the Kind this piece promotes to upon reaching the last row, or None.

        Currently only pawns promote (to queen).
        """
        return Kind.QUEEN if kind is Kind.PAWN else None

    @staticmethod
    def promotion_row(color: Color, height: int) -> int:
        """
        Return the row index at which a pawn of the given color promotes.

        White promotes at row 0 (top), black at row height-1 (bottom).
        """
        return 0 if color is Color.WHITE else height - 1
