"""
Moves log panel: displays algebraic notation move history.
"""
from __future__ import annotations
from typing import Optional

from kungfu_chess.model.piece import Color
from state.game_events import MoveAccepted, GameEvent


class MovesLogPanel:
    """
    Subscribes to MoveAccepted events and maintains separate white/black move logs.

    Converts position-based moves to algebraic notation for display.
    """

    def __init__(self):
        self._white_moves: list[str] = []
        self._black_moves: list[str] = []

    def on_event(self, event: GameEvent) -> None:
        """Handle a game event."""
        if isinstance(event, MoveAccepted):
            from_notation = f"{chr(97 + event.src_pos.col)}{8 - event.src_pos.row}"
            to_notation = f"{chr(97 + event.dst_pos.col)}{8 - event.dst_pos.row}"
            piece_char = event.piece.kind.value
            move_str = f"{piece_char}{from_notation}-{to_notation}"
            if event.piece.color is Color.WHITE:
                self._white_moves.append(move_str)
            else:
                self._black_moves.append(move_str)

    def get_moves(self) -> dict[str, list[str]]:
        """Return the move logs grouped by color."""
        return {
            'white': self._white_moves,
            'black': self._black_moves,
        }
