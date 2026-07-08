from enum import Enum
from dataclasses import dataclass

# --- Display constants ---

CELL_SIZE_PX = 100
"""Width and height of a single board cell in pixels."""

MOVE_DURATION_MS = 1000
"""Time in milliseconds for a piece to travel from its source to its destination."""

JUMP_DURATION_MS = 1000
"""Time in milliseconds a piece remains airborne during a jump."""

# --- Color ---

class Color(Enum):
    """Represents the two player colors."""
    WHITE = 'w'
    BLACK = 'b'

    @staticmethod
    def from_char(char):
        """Return the Color matching a single character ('w' or 'b')."""
        for c in Color:
            if c.value == char:
                return c
        raise ValueError(f"Unknown color char: {char!r}")

# --- Piece value object ---

@dataclass(frozen=True)
class Piece:
    """
    Immutable value object representing a single chess piece.

    Replaces raw strings like 'wR' throughout the codebase, providing
    type safety and a clear API. Supports future binary serialization
    by centralizing the piece representation in one place.
    """
    color: Color
    type: str  # single char: 'K', 'Q', 'R', 'B', 'N', 'P', or any custom type

    def __str__(self):
        """Return the canonical two-character token, e.g. 'wR'."""
        return self.color.value + self.type

    @staticmethod
    def from_token(token):
        """
        Parse a two-character token (e.g. 'wR') into a Piece.

        :param token: Two-character string with color prefix and type suffix.
        """
        return Piece(color=Color.from_char(token[0]), type=token[1])

# --- Per-piece configuration ---
# Drives game logic (royal capture, promotion) without hard-coding piece types.
# To support user-defined games, add new entries here and register a matching
# MovementStrategy via PieceMovementFactory.register_strategy().

PIECE_CONFIG = {
    'K': {'is_royal': True,  'promotes_to': None},
    'Q': {'is_royal': False, 'promotes_to': None},
    'R': {'is_royal': False, 'promotes_to': None},
    'B': {'is_royal': False, 'promotes_to': None},
    'N': {'is_royal': False, 'promotes_to': None},
    'P': {'is_royal': False, 'promotes_to': 'Q'},
}
"""
Maps piece-type characters to their game-logic properties:
  - is_royal:    True if capturing this piece ends the game.
  - promotes_to: Piece type to transform into upon reaching the last row, or None.
"""

VALID_COLORS = {c.value for c in Color}
"""Set of valid color prefix characters for piece tokens."""
