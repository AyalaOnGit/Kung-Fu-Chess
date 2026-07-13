from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from kungfu_chess.model.position import Position
from kungfu_chess.config import (
    REASON_OK, REASON_GAME_OVER, REASON_MOTION_IN_PROGRESS, REASON_EMPTY_SOURCE,
)


@dataclass(frozen=True)
class CommandResult:
    """Result of executing any GameCommand."""
    is_accepted: bool
    reason:      str


class GameCommand(ABC):
    """Base class for all game commands."""

    @abstractmethod
    def execute(self, state, rule_engine, arbiter) -> CommandResult:
        """Execute the command against the given engine internals."""


class MoveCommand(GameCommand):
    """Request to move the piece at src to dest."""

    def __init__(self, src: Position, dest: Position):
        self._src  = src
        self._dest = dest

    def execute(self, state, rule_engine, arbiter) -> CommandResult:
        if state.game_over:
            return CommandResult(False, REASON_GAME_OVER)

        if arbiter.is_piece_in_motion(self._src) or arbiter.has_active_jump(self._src):
            return CommandResult(False, REASON_MOTION_IN_PROGRESS)

        piece = state.board.piece_at(self._src)
        if piece is None:
            return CommandResult(False, REASON_EMPTY_SOURCE)

        if arbiter.is_on_cooldown(piece):
            return CommandResult(False, REASON_MOTION_IN_PROGRESS)

        validation = rule_engine.validate_move(state.board, self._src, self._dest)
        if not validation.is_valid:
            return CommandResult(False, validation.reason)

        arbiter.start_motion(piece, self._src, self._dest)
        return CommandResult(True, REASON_OK)


class JumpCommand(GameCommand):
    """Request to make the piece at cell perform a jump."""

    def __init__(self, cell: Position):
        self._cell = cell

    def execute(self, state, rule_engine, arbiter) -> CommandResult:
        if state.game_over:
            return CommandResult(False, REASON_GAME_OVER)

        if arbiter.is_piece_in_motion(self._cell) or arbiter.has_active_jump(self._cell):
            return CommandResult(False, REASON_MOTION_IN_PROGRESS)

        piece = state.board.piece_at(self._cell)
        if piece is None:
            return CommandResult(False, REASON_EMPTY_SOURCE)

        arbiter.start_jump(piece)
        return CommandResult(True, REASON_OK)
