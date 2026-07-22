"""
Network status panel: tracks the opponent-disconnected auto-resign
countdown for the HUD ("Make a 'count down' on the screen" -- spec item 5).
Networked play only; local hotseat mode has no opponent connection.
"""
from __future__ import annotations

from state.game_events import GameEvent, OpponentDisconnected


class NetworkStatusPanel:
    """
    Subscribes to NetworkGameFacade events. On OpponentDisconnected, starts
    counting down from grace_seconds; any other game event (a move/arrival/
    capture/game-over -- i.e. the opponent is clearly back, or the game
    ended on its own) clears it.
    """

    def __init__(self):
        self._remaining_seconds: float | None = None

    def on_event(self, event: GameEvent) -> None:
        if isinstance(event, OpponentDisconnected):
            self._remaining_seconds = event.grace_seconds
        else:
            self._remaining_seconds = None

    def tick(self, dt_ms: float) -> None:
        if self._remaining_seconds is not None:
            self._remaining_seconds = max(0.0, self._remaining_seconds - dt_ms / 1000.0)

    def get_status_message(self) -> str | None:
        if self._remaining_seconds is None:
            return None
        return f'Opponent disconnected -- auto-resign in {int(self._remaining_seconds)}s'
