from abc import ABC, abstractmethod
from config import Piece


class MovementStrategy(ABC):
    """
    Abstract base class for all piece movement strategies.

    Subclasses implement is_legal to define how a piece may move.
    Set needs_clear_path = True on subclasses that cannot jump over other pieces.
    """

    needs_clear_path = False

    @abstractmethod
    def is_legal(self, board, src, dest, piece, height) -> bool:
        """
        Return True if moving from src to dest is geometrically valid for this piece type.

        Does not check turn order, friendly fire, or game-over — those are handled by GameState.

        :param board: 2-D list of Piece|None representing the current board.
        :param src: (row, col) of the piece being moved.
        :param dest: (row, col) of the target cell.
        :param piece: The Piece object being moved.
        :param height: Number of rows on the board (used by pawn for direction/start-row logic).
        """


class KingMovement(MovementStrategy):
    """Movement strategy for the king: one step in any direction."""

    def is_legal(self, board, src, dest, piece, height) -> bool:
        """Return True if dest is exactly one step away from src in any direction."""
        return max(abs(dest[0] - src[0]), abs(dest[1] - src[1])) <= 1


class KnightMovement(MovementStrategy):
    """Movement strategy for the knight: L-shaped jumps, ignores blocking pieces."""

    def is_legal(self, board, src, dest, piece, height) -> bool:
        """Return True if the move forms a valid L-shape (2+1 or 1+2 squares)."""
        d_row, d_col = abs(dest[0] - src[0]), abs(dest[1] - src[1])
        return (d_row == 1 and d_col == 2) or (d_row == 2 and d_col == 1)


class LinearMovement(MovementStrategy):
    """
    Movement strategy for sliding pieces (rook, bishop, queen).

    Configured at construction time to allow straight moves, diagonal moves, or both.
    Requires a clear path — no jumping over pieces.
    """

    needs_clear_path = True

    def __init__(self, allow_straight: bool, allow_diagonal: bool):
        """
        :param allow_straight: Allow movement along ranks and files (rook-style).
        :param allow_diagonal: Allow movement along diagonals (bishop-style).
        """
        self.allow_straight = allow_straight
        self.allow_diagonal = allow_diagonal

    def is_legal(self, board, src, dest, piece, height) -> bool:
        """
        Return True if the move is along an allowed axis and the path is unobstructed.

        :param board: 2-D list of Piece|None.
        :param src: (row, col) origin.
        :param dest: (row, col) destination.
        :param piece: The Piece being moved (unused here, kept for interface consistency).
        :param height: Board height (unused here, kept for interface consistency).
        """
        d_row, d_col = abs(dest[0] - src[0]), abs(dest[1] - src[1])
        is_straight = (d_row == 0 or d_col == 0)
        is_diagonal = (d_row == d_col)

        if is_straight and not self.allow_straight:
            return False
        if is_diagonal and not self.allow_diagonal:
            return False
        if not is_straight and not is_diagonal:
            return False

        r_step = 1 if dest[0] > src[0] else (-1 if dest[0] < src[0] else 0)
        c_step = 1 if dest[1] > src[1] else (-1 if dest[1] < src[1] else 0)

        curr_r, curr_c = src[0] + r_step, src[1] + c_step
        while (curr_r, curr_c) != dest:
            if board[curr_r][curr_c] is not None:
                return False
            curr_r += r_step
            curr_c += c_step
        return True


class PawnMovement(MovementStrategy):
    """
    Movement strategy for the pawn.

    White pawns move upward (decreasing row index); black pawns move downward.
    Pawns capture diagonally and may move two squares from their starting row.
    """

    def is_legal(self, board, src, dest, piece, height) -> bool:
        """
        Return True if the pawn move is valid according to standard pawn rules.

        Handles: single forward move, double move from start row, diagonal capture.

        :param board: 2-D list of Piece|None.
        :param src: (row, col) of the pawn.
        :param dest: (row, col) of the target cell.
        :param piece: The Piece being moved (provides color without re-reading the board).
        :param height: Board height, used to determine starting row.
        """
        row_diff = dest[0] - src[0]
        d_col = abs(dest[1] - src[1])
        direction = -1 if piece.color.value == 'w' else 1
        start_row = self._start_row(piece.color.value, height)

        if d_col == 0:
            if row_diff == direction:
                return board[dest[0]][dest[1]] is None
            if row_diff == 2 * direction and src[0] == start_row:
                mid_r = src[0] + direction
                return board[mid_r][src[1]] is None and board[dest[0]][dest[1]] is None
        elif d_col == 1 and row_diff == direction:
            target = board[dest[0]][dest[1]]
            return target is not None and target.color != piece.color
        return False

    @staticmethod
    def _start_row(color, height):
        """
        Return the starting row index for a pawn of the given color.

        White starts on the second-to-last row; black starts on row 1.

        :param color: 'w' or 'b'.
        :param height: Total number of rows on the board.
        """
        return height - 2 if color == 'w' else 1
