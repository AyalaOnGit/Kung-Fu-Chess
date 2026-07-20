"""
Translates game/events.py dataclasses (which carry kungfu_chess.model
objects) into JSON-safe wire dicts.

network/ must not import kungfu_chess directly — game/ is the only
package that does (§1 of the blueprint). This module is the seam that
lets network/dispatch.py broadcast game events without ever touching a
Piece, Position, Color, or Kind object itself.
"""
from __future__ import annotations
import game.engine_path  # noqa: F401  (must run before any kungfu_chess import)

from typing import Any, Dict, Optional, Tuple

from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position

from game.events import (
    GameEvent, GameOver, JumpAccepted, MoveAccepted, PieceArrived, PieceCaptured, Promotion,
)


def _position(pos: Position) -> list:
    return [pos.row, pos.col]


def _piece(piece: Optional[Piece]) -> Optional[Dict[str, Any]]:
    if piece is None:
        return None
    return {
        'id': piece.id,
        'color': piece.color.value,
        'kind': piece.kind.value,
        'cell': _position(piece.cell),
    }


def to_wire(event: GameEvent) -> Tuple[str, Dict[str, Any]]:
    """Return (envelope_type, data) ready to hand to core.protocol.Envelope."""
    if isinstance(event, MoveAccepted):
        return 'move_accepted', {
            'piece': _piece(event.piece), 'src': _position(event.src), 'dest': _position(event.dest),
        }
    if isinstance(event, JumpAccepted):
        return 'jump_accepted', {'piece': _piece(event.piece), 'cell': _position(event.cell)}
    if isinstance(event, PieceArrived):
        return 'piece_arrived', {'piece': _piece(event.piece), 'pos': _position(event.pos)}
    if isinstance(event, PieceCaptured):
        return 'piece_captured', {
            'piece': _piece(event.piece), 'capturer': _piece(event.capturer), 'pos': _position(event.pos),
        }
    if isinstance(event, Promotion):
        return 'promotion', {
            'piece': _piece(event.piece), 'old_kind': event.old_kind.value, 'new_kind': event.new_kind.value,
        }
    if isinstance(event, GameOver):
        return 'game_over', {'winner': event.winner.value, 'loser': event.loser.value}
    raise ValueError(f'unknown game event type: {type(event)!r}')
