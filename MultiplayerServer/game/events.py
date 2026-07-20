"""
Events published onto the Bus by game/engine_bridge.py's EngineEventRelay.

Shape mirrors UI/state/game_events.py, which solves the identical problem
client-side (kungfu_chess's GameEngine emits no events of its own — both
sides infer them by diffing kungfu_chess.observation.snapshot_diff
snapshots, see engine_bridge.py). These are independent dataclasses, not a
shared import, since MultiplayerServer/ and UI/ are independent top-level
packages by design.
"""
from __future__ import annotations
import game.engine_path  # noqa: F401  (must run before any kungfu_chess import)

from dataclasses import dataclass
from typing import Optional
from kungfu_chess.model.piece import Piece, Color, Kind
from kungfu_chess.model.position import Position


@dataclass
class MoveAccepted:
    """A move command passed authorization and was accepted by the engine.
    Fires immediately on acceptance — before the piece has finished
    travelling. PieceArrived (below) fires later, once it actually lands."""
    piece: Piece
    src: Position
    dest: Position


@dataclass
class JumpAccepted:
    """A jump command passed authorization and was accepted by the engine."""
    piece: Piece
    cell: Position


@dataclass
class PieceArrived:
    """A piece completed its motion and arrived at destination."""
    piece: Piece
    pos: Position


@dataclass
class PieceCaptured:
    """A piece was captured."""
    piece: Piece
    capturer: Optional[Piece]
    pos: Position


@dataclass
class Promotion:
    """A pawn reached the far end and was promoted."""
    piece: Piece
    old_kind: Kind
    new_kind: Kind


@dataclass
class GameOver:
    """The game ended (king captured)."""
    winner: Color
    loser: Color


GameEvent = MoveAccepted | JumpAccepted | PieceArrived | PieceCaptured | Promotion | GameOver
