from itertools import count
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece, Color, Kind
from kungfu_chess.model.board import Board

_id_counter = count(1)

def new_piece(color: Color, kind: Kind, row: int, col: int) -> Piece:
    return Piece(id=next(_id_counter), color=color, kind=kind, cell=Position(row, col))

def W(kind: Kind, row: int, col: int) -> Piece:
    return new_piece(Color.WHITE, kind, row, col)

def B(kind: Kind, row: int, col: int) -> Piece:
    return new_piece(Color.BLACK, kind, row, col)

def empty_board(w=8, h=8) -> Board:
    return Board(width=w, height=h)

def board_with(*pieces) -> Board:
    b = empty_board()
    for p in pieces:
        b.add_piece(p)
    return b
