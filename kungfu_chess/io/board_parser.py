from __future__ import annotations
from itertools import count
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece, Color, Kind
from kungfu_chess.model.board import Board

_COLOR_MAP = {c.value: c for c in Color}
_KIND_MAP  = {k.value: k for k in Kind}
_id_counter = count(1)


def parse_board(lines: list[str]) -> Board:
    """
    Parse a list of text rows into a Board.

    Each token is either '.' (empty) or a two-character piece token (e.g. 'wR').
    Raises ValueError on unknown tokens or inconsistent row widths.

    :param lines: Non-empty list of board row strings.
    :return: Populated Board.
    """
    rows = [line.split() for line in lines if line.split()]
    if not rows:
        raise ValueError("Board definition is empty.")

    width  = len(rows[0])
    height = len(rows)

    for i, row in enumerate(rows):
        if len(row) != width:
            raise ValueError("ERROR ROW_WIDTH_MISMATCH")

    board = Board(width=width, height=height)

    for r, row in enumerate(rows):
        for c, token in enumerate(row):
            if token == '.':
                continue
            if len(token) != 2 or token[0] not in _COLOR_MAP or token[1] not in _KIND_MAP:
                raise ValueError("ERROR UNKNOWN_TOKEN")
            piece = Piece(
                id=next(_id_counter),
                color=_COLOR_MAP[token[0]],
                kind=_KIND_MAP[token[1]],
                cell=Position(r, c),
            )
            board.add_piece(piece)

    return board
