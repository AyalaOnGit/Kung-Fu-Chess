"""
Game events: dataclasses for UI events.

Published by GameFacade and observed by UI components.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece, Color, Kind


@dataclass
class MoveAccepted:
    """A move command was accepted by the engine."""
    piece: Piece
    src_pos: Position
    dst_pos: Position


@dataclass
class MoveRejected:
    """A move command was rejected by the engine."""
    piece: Piece
    reason: str  # e.g. 'illegal_piece_move', 'game_over'


@dataclass
class PieceArrived:
    """A piece completed its motion and arrived at destination."""
    piece: Piece
    pos: Position


@dataclass
class PieceCaptured:
    """An opponent's piece was captured."""
    piece: Piece
    capturer: Piece  # the piece that captured it
    pos: Position


@dataclass
class PieceHalted:
    """A mid-flight piece was halted (same-color move destination taken)."""
    piece: Piece
    halted_at: Position  # where it was stopped


@dataclass
class Promotion:
    """A pawn reached the far end and was promoted."""
    piece: Piece
    old_kind: Kind
    new_kind: Kind
    pos: Position


@dataclass
class GameOver:
    """The game ended (king captured)."""
    winner: Color  # the winning player's color
    loser: Color


@dataclass
class OpponentDisconnected:
    """The opponent's connection dropped; the server will auto-resign them
    on its own timer if they don't reconnect within grace_seconds. Only
    published by NetworkGameFacade (networked play) -- local hotseat mode
    has no opponent connection to lose."""
    grace_seconds: float


@dataclass
class OpponentJoined:
    """A player took the room's other seat (white or black). Only published
    by NetworkGameFacade -- local hotseat mode has both seats filled from
    the start, so there's never a seat to wait on."""
    role: str  # 'white' or 'black'
    username: str
    elo: Optional[int]


@dataclass
class RatingUpdate:
    """Both players' ELO before/after a just-recorded rated match result.
    Arrives as its own envelope, separately from (and with no ordering
    guarantee relative to) GameOver -- see MultiplayerServer/main.py's
    on_game_over for why. Only published by NetworkGameFacade -- local
    hotseat mode has no persisted, rated accounts."""
    white_elo_before: int
    white_elo_after: int
    black_elo_before: int
    black_elo_after: int


@dataclass(frozen=True)
class GameOverInfo:
    """Everything HudRenderer needs to draw the end-of-game dialog.

    Not a GameEvent itself (nothing publishes it) -- ui_components/
    game_over_banner.py composes it from GameOver + RatingUpdate. Lives
    here rather than in game_over_banner.py so graphics/hud_renderer.py
    can depend on state/ for it instead of reaching into ui_components/."""
    title: str
    white_label: Optional[str] = None
    black_label: Optional[str] = None
    white_delta: Optional[int] = None
    black_delta: Optional[int] = None


# Union type for all possible events
GameEvent = (
    MoveAccepted | MoveRejected | PieceArrived | PieceCaptured |
    PieceHalted | Promotion | GameOver | OpponentDisconnected | OpponentJoined | RatingUpdate
)
