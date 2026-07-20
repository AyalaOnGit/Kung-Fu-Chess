"""
Authorization gate + engine invocation (§2 of the blueprint).

The single place server code decides "is this call allowed," independent
of transport — these functions take plain data and a GameEngine; they
know nothing about sockets, envelopes, or websockets.

Pipeline for both handle_move and handle_jump, in order:
  1. Role gate — NOT_IN_A_MATCH if session.role is None (not currently
     paired into a match; Phase 3 on), else the viewer short-circuit
     (session.role.can_move) — before anything else.
  2. Parse the wire payload into Position(s). Malformed -> MALFORMED_COMMAND.
  3. Ownership check against the live board — the actual anti-cheat gate,
     since neither kungfu_chess.rules.rule_engine.RuleEngine nor
     kungfu_chess.engine.commands.MoveCommand/JumpCommand check who a piece
     belongs to (confirmed by reading both this session).
  4. Optional piece_kind integrity check — defense in depth only.
  5. engine.execute(...); on acceptance, publish to the Bus and return
     success; on rejection, translate the engine's reason to an ErrorCode
     and return it to the caller alone (never broadcast).
"""
from __future__ import annotations
import game.engine_path  # noqa: F401  (must run before any kungfu_chess import)

from dataclasses import dataclass
from typing import Any, Optional, Tuple

from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.engine.commands import MoveCommand, JumpCommand
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position

from core.bus import AsyncMessageBus
from core.protocol import ErrorCode
from network.session import ClientSession
from game.events import MoveAccepted, JumpAccepted


@dataclass(frozen=True)
class HandleResult:
    """Outcome of handling one move/jump request, for the caller alone."""
    accepted: bool
    error: Optional[ErrorCode] = None


def _parse_position(value: Any) -> Optional[Position]:
    """Parse a wire [row, col] pair into a Position, or None if malformed."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    row, col = value
    if isinstance(row, bool) or isinstance(col, bool):
        return None
    if not isinstance(row, int) or not isinstance(col, int):
        return None
    return Position(row, col)


def _role_gate(session: ClientSession) -> Optional[ErrorCode]:
    """Step 1: None if session may act at all, else the ErrorCode to reject with."""
    if session.role is None:
        return ErrorCode.NOT_IN_A_MATCH
    if not session.role.can_move:
        return ErrorCode.VIEWER_READ_ONLY
    return None


def _authorize(session: ClientSession, engine: GameEngine, position: Position,
               claimed_kind: Any) -> Tuple[Optional[Piece], Optional[ErrorCode]]:
    """
    Steps 3-4: the piece at position must exist, belong to session's role,
    and (if the caller claimed a kind) match it. Returns (piece, None) on
    success or (None, ErrorCode) on failure.
    """
    piece = engine.board.piece_at(position)
    if piece is None:
        return None, ErrorCode.EMPTY_SOURCE
    # .name, not .value: kungfu_chess.model.piece.Color uses 'w'/'b' for its
    # wire-shorthand, Role uses 'white'/'black' for ours — they only agree
    # on the member spelling (WHITE/BLACK), not the value.
    if piece.color.name != session.role.name:
        return None, ErrorCode.NOT_YOUR_PIECE
    if claimed_kind is not None and claimed_kind != piece.kind.value:
        return None, ErrorCode.PIECE_MISMATCH
    return piece, None


def handle_move(session: ClientSession, engine: GameEngine, bus: AsyncMessageBus,
                 topic: str, data: dict) -> HandleResult:
    """
    :param data: decoded envelope data —
        {'src': [row, col], 'dest': [row, col], 'piece_kind'?: str}
    """
    gate_error = _role_gate(session)
    if gate_error is not None:
        return HandleResult(accepted=False, error=gate_error)

    src = _parse_position(data.get('src'))
    dest = _parse_position(data.get('dest'))
    if src is None or dest is None:
        return HandleResult(accepted=False, error=ErrorCode.MALFORMED_COMMAND)

    piece, error = _authorize(session, engine, src, data.get('piece_kind'))
    if error is not None:
        return HandleResult(accepted=False, error=error)

    result = engine.execute(MoveCommand(src, dest))
    if not result.is_accepted:
        return HandleResult(accepted=False, error=ErrorCode(result.reason))

    bus.publish(topic, MoveAccepted(piece=piece, src=src, dest=dest))
    return HandleResult(accepted=True)


def handle_jump(session: ClientSession, engine: GameEngine, bus: AsyncMessageBus,
                 topic: str, data: dict) -> HandleResult:
    """
    :param data: decoded envelope data — {'cell': [row, col], 'piece_kind'?: str}
    """
    gate_error = _role_gate(session)
    if gate_error is not None:
        return HandleResult(accepted=False, error=gate_error)

    cell = _parse_position(data.get('cell'))
    if cell is None:
        return HandleResult(accepted=False, error=ErrorCode.MALFORMED_COMMAND)

    piece, error = _authorize(session, engine, cell, data.get('piece_kind'))
    if error is not None:
        return HandleResult(accepted=False, error=error)

    result = engine.execute(JumpCommand(cell))
    if not result.is_accepted:
        return HandleResult(accepted=False, error=ErrorCode(result.reason))

    bus.publish(topic, JumpAccepted(piece=piece, cell=cell))
    return HandleResult(accepted=True)
