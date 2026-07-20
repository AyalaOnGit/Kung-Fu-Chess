from __future__ import annotations
from kungfu_chess.model.board import Board
from kungfu_chess.io.board_parser import parse_board

_STANDARD_START = [
    "bR bN bB bQ bK bB bN bR",
    "bP bP bP bP bP bP bP bP",
    ".  .  .  .  .  .  .  .  ",
    ".  .  .  .  .  .  .  .  ",
    ".  .  .  .  .  .  .  .  ",
    ".  .  .  .  .  .  .  .  ",
    "wP wP wP wP wP wP wP wP",
    "wR wN wB wQ wK wB wN wR",
]


def standard_board() -> Board:
    """Return a fresh Board set up in the standard 8x8 chess starting position."""
    return parse_board(_STANDARD_START)
