from __future__ import annotations
from kungfu_chess.model.board import Board
from kungfu_chess.model.position import Position


def board_to_lines(board: Board) -> list[str]:
    """
    Convert the logical board state to a list of display strings.

    Each row is a space-separated string of tokens ('wR', 'bK', '.', …).
    Moving pieces are shown at their source cell (logical occupancy).

    :param board: The Board to render as text.
    :return: List of strings, one per row.
    """
    rows = []
    for r in range(board.height):
        tokens = []
        for c in range(board.width):
            piece = board.piece_at(Position(r, c))
            tokens.append(piece.token() if piece is not None else '.')
        rows.append(' '.join(tokens))
    return rows


def print_board(board: Board) -> None:
    """Print the logical board state to stdout."""
    for line in board_to_lines(board):
        print(line)
