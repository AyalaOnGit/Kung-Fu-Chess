from abc import ABC, abstractmethod
from config import CELL_SIZE_PX


def pixel_to_cell(x, y):
    """
    Convert pixel coordinates to board cell indices.

    :param x: Horizontal pixel coordinate.
    :param y: Vertical pixel coordinate.
    :return: (row, col) tuple of the corresponding board cell.
    """
    return y // CELL_SIZE_PX, x // CELL_SIZE_PX


class Command(ABC):
    """Abstract base class for all game commands."""

    @abstractmethod
    def execute(self, state, context) -> None:
        """
        Execute the command, mutating state and/or context as needed.

        :param state: The current GameState instance.
        :param context: A dict holding transient UI state (e.g. {'selected': (row, col) | None}).
        """


class WaitCommand(Command):
    """Advance the game clock by a fixed number of milliseconds."""

    def __init__(self, ms):
        """:param ms: Number of milliseconds to advance the clock."""
        self.ms = ms

    def execute(self, state, context):
        """Advance the clock by self.ms and resolve any moves that have now arrived."""
        state.clock += self.ms
        state.update_time()


class PrintBoardCommand(Command):
    """Print the current board to stdout, one row per line, tokens separated by spaces."""

    def execute(self, state, context):
        """Resolve pending moves, then print each board row."""
        state.update_time()
        for row in state.get_board_rows():
            print(" ".join(row))


class JumpCommand(Command):
    """Make the piece at the given pixel coordinates perform a jump."""

    def __init__(self, x, y):
        """
        :param x: Horizontal pixel coordinate of the target cell.
        :param y: Vertical pixel coordinate of the target cell.
        """
        self.x, self.y = x, y

    def execute(self, state, context):
        """
        Enqueue a jump for the piece at the cell corresponding to (x, y).

        Ignored if: game is over, coordinates are out of bounds, the piece is
        already moving, the piece is already airborne, or the cell is empty.
        """
        if state.game_over:
            return
        state.update_time()

        row, col = pixel_to_cell(self.x, self.y)
        if not state.in_bounds(row, col):
            return
        if state.is_piece_moving((row, col)) or state.is_piece_jumping((row, col)):
            return

        piece = state.get_piece(row, col)
        if piece is not None:
            state.enqueue_jump((row, col), piece)
            context['selected'] = None


class ClickCommand(Command):
    """Handle a board click: select a piece or issue a move command."""

    def __init__(self, x, y):
        """
        :param x: Horizontal pixel coordinate of the clicked cell.
        :param y: Vertical pixel coordinate of the clicked cell.
        """
        self.x, self.y = x, y

    def execute(self, state, context):
        """
        Process a click at (x, y).

        - Clicking a piece with nothing selected: selects it.
        - Clicking a friendly piece with one already selected: switches selection.
        - Clicking an enemy piece or empty cell with a piece selected: enqueues a move.
        - Out-of-bounds clicks and clicks on moving pieces are silently ignored.
        """
        if state.game_over:
            return
        state.update_time()

        row, col = pixel_to_cell(self.x, self.y)
        if not state.in_bounds(row, col):
            return
        if state.is_piece_moving((row, col)):
            return
        if context['selected'] is None and state.is_piece_jumping((row, col)):
            return

        clicked = state.get_piece(row, col)
        selected = context['selected']

        if clicked is not None:
            selected_piece = state.get_piece(*selected) if selected else None
            if selected_piece is None or selected_piece.color == clicked.color:
                context['selected'] = (row, col)
            else:
                if state.is_legal_move(selected, (row, col)):
                    state.enqueue_move(selected, (row, col), state.get_piece(*selected))
                context['selected'] = None
        else:
            if selected is not None:
                if state.is_legal_move(selected, (row, col)):
                    state.enqueue_move(selected, (row, col), state.get_piece(*selected))
                context['selected'] = None
