"""
Game events: dataclasses for UI events.

Published by GameFacade and observed by UI components.
"""
from __future__ import annotations
from dataclasses import dataclass
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


# Union type for all possible events
GameEvent = (
    MoveAccepted | MoveRejected | PieceArrived | PieceCaptured |
    PieceHalted | Promotion | GameOver
)
