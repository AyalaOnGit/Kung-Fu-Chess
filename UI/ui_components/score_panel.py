"""
Score panel: tracks captured pieces and calculates material score.
"""
from __future__ import annotations
from collections import defaultdict

from kungfu_chess.model.piece import Color, Kind
from state.game_events import PieceCaptured, GameEvent


class ScorePanel:
    """
    Subscribes to PieceCaptured events and tracks material score.
    
    Assigns values: Pawn=1, Knight=3, Bishop=3, Rook=5, Queen=9, King=∞
    """
    
    PIECE_VALUES = {
        Kind.PAWN: 1,
        Kind.KNIGHT: 3,
        Kind.BISHOP: 3,
        Kind.ROOK: 5,
        Kind.QUEEN: 9,
        Kind.KING: 999,
    }
    
    def __init__(self):
        self._captured_by_color = defaultdict(int)  # Color -> total value
    
    def on_event(self, event: GameEvent) -> None:
        """Handle a game event."""
        if isinstance(event, PieceCaptured):
            # Add capture value to capturer's side
            value = self.PIECE_VALUES.get(event.piece.kind, 0)
            if event.capturer:
                self._captured_by_color[event.capturer.color] += value
    
    def get_score(self, color: Color) -> int:
        """Get captured material score for a player."""
        return self._captured_by_color[color]
