from __future__ import annotations
from kungfu_chess.model.board import Board
from kungfu_chess.model.game_state import GameState
from kungfu_chess.model.piece import Piece
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.realtime.real_time_arbiter import RealTimeArbiter
from kungfu_chess.engine.commands import GameCommand, CommandResult
from kungfu_chess.config import CELL_SIZE_PX, PIECE_SPEED_PPS


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
        self._check_path_blocks()
        self._arbiter.advance_time(ms)

    def _check_path_blocks(self) -> None:
        """
        Dynamically shorten any in-flight sliding motion whose path has
        become obstructed since the move was issued.

        Called once per tick, before advance_time resolves arrivals.

        A cell is considered occupied if:
          - A piece is currently sitting there on the board (static), OR
          - Another in-flight motion has that cell as its dest (will arrive there).

        Rules:
          - Knight paths have no intermediate cells → never blocked mid-path.
          - Scan each path cell the piece hasn't passed yet.
          - Friendly blocker → stop one cell before it.
          - Enemy blocker → stop on it (capture on arrival).
          - Only redirect if new_dest differs from current dest.
        """
        active = self._arbiter.get_active_motions()

        # Build a map: dest_position -> piece color, for all in-flight motions
        # (so we can treat "piece about to arrive at X" as an occupant of X)
        motion_dests: dict = {}
        for m in active:
            motion_dests[m.dest] = m.piece.color

        for motion in active:
            path = motion.path
            if len(path) <= 1:
                continue

            board = self._state.board
            current_idx = motion.current_step(self._arbiter.clock_ms)

            new_dest = None
            for i, cell in enumerate(path):
                if i < current_idx:
                    continue  # already passed

                # Check static board occupant
                occupant = board.piece_at(cell)
                occupant_color = None
                if occupant is not None:
                    occupant_color = occupant.color
                elif cell in motion_dests and cell != motion.dest:
                    # Another piece is flying toward this cell
                    occupant_color = motion_dests[cell]

                if occupant_color is None:
                    continue

                if occupant_color == motion.piece.color:
                    # Friendly → stop one cell before
                    new_dest = path[i - 1] if i > 0 else motion.src
                else:
                    # Enemy → stop on this cell (capture)
                    new_dest = cell
                break

            if new_dest is not None and new_dest != motion.dest:
                self._arbiter.redirect_motion(motion, new_dest)

    def _on_piece_captured(self, piece: Piece) -> None:
        """Notified for every capture; only ending the game for a king is
        chess-specific knowledge, so it lives here rather than in the
        rule-agnostic RealTimeArbiter."""
        if Piece.is_royal(piece.kind):
            self._state.game_over = True

    def _on_piece_arrived(self, piece: Piece) -> None:
        piece.try_promote(self._state.board.height)

    def get_cooldown_ratio(self, piece) -> float:
        """Return fraction of cooldown remaining for piece (1.0=just started, 0.0=done)."""
        return self._arbiter.cooldown_ratio_for(piece)

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
