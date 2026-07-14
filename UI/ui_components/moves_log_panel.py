"""
Moves log panel: displays algebraic notation move history.
"""
from __future__ import annotations
from typing import Optional

from state.game_events import MoveAccepted, GameEvent


class MovesLogPanel:
    """
    Subscribes to MoveAccepted events and maintains a move log.
    
    Converts position-based moves to algebraic notation for display.
    """
    
    def __init__(self):
        self._moves = []
    
    def on_event(self, event: GameEvent) -> None:
        """Handle a game event."""
        if isinstance(event, MoveAccepted):
            # Format as algebraic notation
            from_notation = f"{chr(97 + event.src_pos.col)}{8 - event.src_pos.row}"
            to_notation = f"{chr(97 + event.dst_pos.col)}{8 - event.dst_pos.row}"
            piece_char = event.piece.kind.value
            move_str = f"{piece_char}{from_notation}-{to_notation}"
            self._moves.append(move_str)
    
    def get_moves(self) -> list[str]:
        """Return the move log."""
        return self._moves
