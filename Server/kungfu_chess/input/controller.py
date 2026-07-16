from __future__ import annotations
from typing import Optional
from kungfu_chess.model.position import Position
from kungfu_chess.input.board_mapper import BoardMapper
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.engine.commands import MoveCommand, JumpCommand


class Controller:
    """
    Translates user click actions into GameEngine commands.

    Selection policy:
      - First click on a piece: select it.
      - First click on an empty cell: ignore.
      - Second click (any in-board cell): call request_move, then clear selection.
      - Out-of-bounds click with no selection: ignore.
      - Out-of-bounds click with a selection: cancel selection, send no command.

    Does not decide chess legality, mutate Board, or handle rendering.
    """

    def __init__(self, engine: GameEngine, mapper: BoardMapper):
        self._engine:   GameEngine       = engine
        self._mapper:   BoardMapper      = mapper
        self._selected: Optional[Position] = None

    def on_click(self, x: int, y: int) -> tuple[None | tuple[CommandResult, Position, Position, Piece], None | Position, None | Position]:
        """Process a click at pixel (x, y)."""
        if not self._mapper.in_bounds_px(x, y):
            self._selected = None
            return None, None, None

        pos = self._mapper.pixel_to_position(x, y)

        if self._selected is None:
            piece = self._engine.board.piece_at(pos)
            if piece is not None:
                self._selected = pos
            return None, None, None
        else:
            clicked        = self._engine.board.piece_at(pos)
            selected_piece = self._engine.board.piece_at(self._selected)

            # Re-select only if: clicked a friendly piece AND the original
            # selected piece is still on the board (not in-flight).
            if (clicked is not None
                    and selected_piece is not None
                    and clicked.color == selected_piece.color):
                self._selected = pos
                return None, None, None

            # Otherwise: attempt the move (covers enemy target, empty target,
            # and the case where the selected piece already flew away).
            piece  = selected_piece  # may be None if piece is in-flight
            result = self._engine.execute(MoveCommand(self._selected, pos))
            src    = self._selected
            dst    = pos
            self._selected = None
            return (result, src, dst, piece), src, dst

    def on_jump(self, x: int, y: int):
        """Process a jump command at pixel (x, y). Returns CommandResult."""
        if not self._mapper.in_bounds_px(x, y):
            return None
        pos = self._mapper.pixel_to_position(x, y)
        result = self._engine.execute(JumpCommand(pos))
        self._selected = None
        return result

    @property
    def selected(self) -> Optional[Position]:
        """The currently selected cell, or None."""
        return self._selected
