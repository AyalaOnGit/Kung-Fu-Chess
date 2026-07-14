from __future__ import annotations
from dataclasses import dataclass
from kungfu_chess.model.board import Board
from kungfu_chess.model.position import Position
from kungfu_chess.rules.piece_rules import get_rule
from kungfu_chess.config import (
    REASON_OK, REASON_OUTSIDE_BOARD, REASON_EMPTY_SOURCE,
    REASON_FRIENDLY_DEST, REASON_ILLEGAL_MOVE,
)


@dataclass(frozen=True)
class MoveValidation:
    """Result of a rule-level move validation."""
    is_valid: bool
    reason:   str   # 'ok' | 'outside_board' | 'empty_source' | 'friendly_destination' | 'illegal_piece_move'


class RuleEngine:
    """
    Validates whether a requested move is legal given the current board state.

    Read-only: never mutates Board, never starts motions, never sets game_over.
    Game-over is handled by GameEngine before RuleEngine is ever called.
    """

    def validate_move(self, board: Board, src: Position, dest: Position) -> MoveValidation:
        """
        Return MoveValidation for moving the piece at src to dest.

        :param board: Current board state (read-only).
        :param src:   Source cell.
        :param dest:  Destination cell.
        """
        if not board.in_bounds(src) or not board.in_bounds(dest):
            return MoveValidation(False, REASON_OUTSIDE_BOARD)

        piece = board.piece_at(src)
        if piece is None:
            return MoveValidation(False, REASON_EMPTY_SOURCE)

        occupant = board.piece_at(dest)
        if occupant is not None and occupant.color == piece.color:
            return MoveValidation(False, REASON_FRIENDLY_DEST)

        rule = get_rule(piece.kind)
        if dest not in rule.legal_destinations(board, piece):
            return MoveValidation(False, REASON_ILLEGAL_MOVE)

        return MoveValidation(True, REASON_OK)
