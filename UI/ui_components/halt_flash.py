"""
Halt flash: brief red overlay when a piece is halted mid-flight.
"""
from __future__ import annotations

from state.game_events import PieceHalted, GameEvent
from ui_config import HALT_FLASH_DURATION_MS


class HaltFlashTracker:
    """
    Subscribes to PieceHalted event and tracks halt flash state.
    """

    def __init__(self, flash_duration_ms: float = HALT_FLASH_DURATION_MS):
        self._flash_duration = flash_duration_ms
        self._halted_piece_id: int | None = None
        self._halt_elapsed: float = 0.0
    
    def on_event(self, event: GameEvent) -> None:
        """Handle a game event."""
        if isinstance(event, PieceHalted):
            self._halted_piece_id = event.piece.id
            self._halt_elapsed = 0.0
    
    def tick(self, dt_ms: float) -> None:
        """Advance halt flash."""
        if self._halted_piece_id is not None:
            self._halt_elapsed += dt_ms
            if self._halt_elapsed >= self._flash_duration:
                self._halted_piece_id = None
    
    def is_flashing(self) -> bool:
        """Return True if a halt flash is currently active."""
        return self._halted_piece_id is not None
    
    def get_flashing_piece_id(self) ->int | None:
        """Get the piece ID currently flashing, or None."""
        return self._halted_piece_id
