"""
Game over banner: displays end-of-game message.
"""
from __future__ import annotations

from state.game_events import GameOver, GameEvent


class GameOverBanner:
    """
    Subscribes to GameOver event and displays winner/loser.
    """
    
    def __init__(self):
        self._game_over = False
        self._message = ""
    
    def on_event(self, event: GameEvent) -> None:
        """Handle a game event."""
        if isinstance(event, GameOver):
            self._game_over = True
            self._message = f"Game Over! {event.winner.value.upper()} wins!"
    
    def should_display(self) -> bool:
        """Return True if banner should be shown."""
        return self._game_over
    
    def get_message(self) -> str:
        """Get the banner message."""
        return self._message
