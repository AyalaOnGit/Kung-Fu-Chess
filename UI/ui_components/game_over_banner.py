"""
Game over banner: composes the end-of-game dialog's content -- winner (or
draw), plus each player's ELO change once a rating_update arrives.

GameOver and RatingUpdate reach here as two independent events with no
ordering guarantee between them (see MultiplayerServer/main.py's
on_game_over docstring), so get_info() just reflects whatever has arrived
so far; the rating lines simply stay blank until RatingUpdate lands.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from kungfu_chess.model.piece import Color
from state.game_events import GameEvent, GameOver, RatingUpdate


@dataclass(frozen=True)
class GameOverInfo:
    """Everything HudRenderer needs to draw the end-of-game dialog."""
    title: str
    white_label: Optional[str] = None
    black_label: Optional[str] = None
    white_delta: Optional[int] = None
    black_delta: Optional[int] = None


class GameOverBanner:
    """Subscribes to GameOver/RatingUpdate and composes a GameOverInfo for
    HudRenderer. white_name/black_name are display names only (local
    hotseat mode passes the generic "White"/"Black" -- see main.py)."""

    def __init__(self, white_name: str = 'White', black_name: str = 'Black'):
        self._game_over = False
        self._winner: Optional[Color] = None
        self._white_name = white_name
        self._black_name = black_name
        self._white_elo_before: Optional[int] = None
        self._white_elo_after: Optional[int] = None
        self._black_elo_before: Optional[int] = None
        self._black_elo_after: Optional[int] = None

    def on_event(self, event: GameEvent) -> None:
        """Handle a game event."""
        if isinstance(event, GameOver):
            self._game_over = True
            self._winner = event.winner
        elif isinstance(event, RatingUpdate):
            self._white_elo_before = event.white_elo_before
            self._white_elo_after = event.white_elo_after
            self._black_elo_before = event.black_elo_before
            self._black_elo_after = event.black_elo_after

    def get_info(self) -> Optional[GameOverInfo]:
        """The dialog's content, or None if the game isn't over yet."""
        if not self._game_over:
            return None

        # winner is always a Color today (kung-fu chess ends by king
        # capture or resignation, never a draw) -- guarded anyway so a
        # future draw-capable winner=None wouldn't crash the dialog.
        if self._winner is None:
            title = 'Draw!'
        else:
            winner_name = self._white_name if self._winner is Color.WHITE else self._black_name
            title = f'{winner_name} wins!'

        white_label = black_label = None
        white_delta = black_delta = None
        if self._white_elo_after is not None and self._black_elo_after is not None:
            white_delta = self._white_elo_after - self._white_elo_before
            black_delta = self._black_elo_after - self._black_elo_before
            white_label = f'{self._white_name}: {self._white_elo_after} ({white_delta:+d})'
            black_label = f'{self._black_name}: {self._black_elo_after} ({black_delta:+d})'

        return GameOverInfo(title=title, white_label=white_label, black_label=black_label,
                             white_delta=white_delta, black_delta=black_delta)
