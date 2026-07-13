from __future__ import annotations
from kungfu_chess.model.board import Board
from kungfu_chess.model.game_state import GameState
from kungfu_chess.model.piece import Piece
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.realtime.real_time_arbiter import RealTimeArbiter
from kungfu_chess.engine.commands import GameCommand, CommandResult


class GameEngine:
    """
    Application-service coordinator.

    Responsibilities:
      - Accept and execute GameCommand objects.
      - Advance simulated time via wait().
      - Receive king-capture and piece-arrived notifications (private).

    Does not contain piece-specific movement logic, pixel mapping,
    rendering, text parsing, or test-runner logic.
    """

    def __init__(self, game_state: GameState, rule_engine: RuleEngine,
                 arbiter: RealTimeArbiter):
        self._state       = game_state
        self._rule_engine = rule_engine
        self._arbiter     = arbiter

    def execute(self, command: GameCommand) -> CommandResult:
        """Execute a GameCommand and return its result."""
        return command.execute(self._state, self._rule_engine, self._arbiter)

    def wait(self, ms: int) -> None:
        """Advance simulated time by ms milliseconds."""
        self._arbiter.advance_time(ms)

    def _on_king_captured(self) -> None:
        self._state.game_over = True

    def _on_piece_arrived(self, piece: Piece) -> None:
        piece.try_promote(self._state.board.height)

    def force_game_over(self) -> None:
        """Force game_over state — intended for testing only."""
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
