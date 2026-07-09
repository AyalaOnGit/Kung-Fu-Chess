from __future__ import annotations
from dataclasses import dataclass
from kungfu_chess.model.board import Board
from kungfu_chess.model.game_state import GameState
from kungfu_chess.model.position import Position
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.realtime.real_time_arbiter import RealTimeArbiter
from kungfu_chess.config import (
    REASON_OK, REASON_GAME_OVER, REASON_MOTION_IN_PROGRESS, REASON_EMPTY_SOURCE,
)


@dataclass(frozen=True)
class MoveResult:
    """Result of a GameEngine.request_move call."""
    is_accepted: bool
    reason:      str  # 'ok' | 'game_over' | 'motion_in_progress' | rule-level reason


class GameEngine:
    """
    Application-service coordinator.

    Responsibilities:
      - Enforce game_over guard before any move.
      - Enforce one-active-motion policy.
      - Delegate move validation to RuleEngine.
      - Start validated motions through RealTimeArbiter.
      - Delegate wait(ms) to RealTimeArbiter.
      - Receive king-capture notification and set game_over.

    Does not contain piece-specific movement logic, pixel mapping,
    rendering, text parsing, or test-runner logic.
    """

    def __init__(self, game_state: GameState, rule_engine: RuleEngine,
                 arbiter: RealTimeArbiter):
        self._state       = game_state
        self._rule_engine = rule_engine
        self._arbiter     = arbiter

    # --- Public command boundary ---

    def request_move(self, src: Position, dest: Position) -> MoveResult:
        """
        Attempt to move the piece at src to dest.

        Guards (in order):
          1. game_over
          2. piece at src is already in motion or jumping
          3. same-color motion already active (one motion per color)
          4. RuleEngine validation

        :return: MoveResult with is_accepted and reason.
        """
        if self._state.game_over:
            return MoveResult(False, REASON_GAME_OVER)

        if self._arbiter.is_piece_in_motion(src) or self._arbiter.has_active_jump(src):
            return MoveResult(False, REASON_MOTION_IN_PROGRESS)

        piece = self._state.board.piece_at(src)
        if piece is None:
            return MoveResult(False, REASON_EMPTY_SOURCE)

        if self._arbiter.has_active_motion():
            return MoveResult(False, REASON_MOTION_IN_PROGRESS)

        validation = self._rule_engine.validate_move(self._state.board, src, dest)
        if not validation.is_valid:
            return MoveResult(False, validation.reason)

        self._arbiter.start_motion(piece, src, dest)
        return MoveResult(True, REASON_OK)

    def request_jump(self, cell: Position) -> MoveResult:
        """
        Attempt to make the piece at cell perform a jump.

        :return: MoveResult with is_accepted and reason.
        """
        if self._state.game_over:
            return MoveResult(False, REASON_GAME_OVER)

        if self._arbiter.is_piece_in_motion(cell) or self._arbiter.has_active_jump(cell):
            return MoveResult(False, REASON_MOTION_IN_PROGRESS)

        piece = self._state.board.piece_at(cell)
        if piece is None:
            return MoveResult(False, REASON_EMPTY_SOURCE)

        self._arbiter.start_jump(piece)
        return MoveResult(True, REASON_OK)

    def wait(self, ms: int) -> None:
        """Advance simulated time by ms milliseconds."""
        self._arbiter.advance_time(ms)

    def on_king_captured(self) -> None:
        """Called by RealTimeArbiter when a king is captured."""
        self._state.game_over = True

    # --- Read-only access ---

    @property
    def game_over(self) -> bool:
        return self._state.game_over

    @property
    def board(self) -> Board:
        return self._state.board

    @property
    def clock_ms(self) -> int:
        return self._arbiter.clock_ms
