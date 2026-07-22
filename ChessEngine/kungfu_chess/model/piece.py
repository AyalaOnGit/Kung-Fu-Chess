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
    COOLING  = 'cooling'   # post-arrival cooldown, cannot move yet
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

    def begin_move(self) -> None:
        """Transition to MOVING: the piece has started sliding toward a destination."""
        self.state = PieceState.MOVING

    def begin_jump(self) -> None:
        """Transition to JUMPING: the piece is airborne over its own cell."""
        self.state = PieceState.JUMPING

    def begin_cooldown(self) -> None:
        """Transition to COOLING: just arrived, cannot move again until cooldown expires."""
        self.state = PieceState.COOLING

    def settle_idle(self) -> None:
        """Transition to IDLE: ready to receive a new command."""
        self.state = PieceState.IDLE

    def mark_captured(self) -> None:
        """Transition to CAPTURED: removed from play."""
        self.state = PieceState.CAPTURED

    def try_promote(self, board_height: int) -> None:
        """Promote this piece in-place if it has reached its promotion row."""
        target_row = 0 if self.color is Color.WHITE else board_height - 1
        if self.kind is Kind.PAWN and self.cell.row == target_row:
            self.kind = Kind.QUEEN
