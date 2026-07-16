from __future__ import annotations
from typing import Callable, Optional
from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece, PieceState
from kungfu_chess.model.position import Position
from kungfu_chess.realtime.motion import Motion, JumpMotion, CooldownTimer, travel_duration_ms, compute_path
from kungfu_chess.config import JUMP_DURATION_MS, COOLDOWN_MS, CELL_SIZE_PX, PIECE_SPEED_PPS


class RealTimeArbiter:
    """
    Manages active Motion and JumpMotion objects and advances simulated time.

    Responsibilities:
      - Store active motions and jumps outside Board.
      - Resolve arrivals: remove from source, capture at dest, place at dest.
      - Resolve airborne captures: enemy arriving at a jumping piece's cell is captured.
      - Report king captures via on_king_captured callback.
      - Expose whether any motion is currently active (for GameEngine policy).

    Does not contain chess legality logic, rendering, or input handling.
    """

    def __init__(self, board: Board, on_king_captured: Callable[[], None],
                 on_piece_arrived: Callable[[Piece], None],
                 cooldown_ms: int = COOLDOWN_MS,
                 jump_duration_ms: int = JUMP_DURATION_MS):
        self._board             = board
        self._on_king_captured  = on_king_captured
        self._on_piece_arrived  = on_piece_arrived
        self._cooldown_ms       = cooldown_ms
        self._jump_duration_ms  = jump_duration_ms
        self._clock_ms:    int  = 0
        self._motions:     list[Motion]        = []
        self._jumps:       list[JumpMotion]    = []
        self._cooldowns:   list[CooldownTimer] = []

    # --- Public API ---

    @property
    def clock_ms(self) -> int:
        """Current simulated clock in milliseconds."""
        return self._clock_ms

    def has_active_motion(self) -> bool:
        """Return True if any piece is currently in transit."""
        return bool(self._motions)

    def has_active_motion_for_color(self, color) -> bool:
        """Return True if a piece of the given color is currently in transit."""
        return any(m.piece.color == color for m in self._motions)

    def has_active_jump(self, cell: Position) -> bool:
        """Return True if the piece at cell is currently airborne."""
        return any(j.cell == cell for j in self._jumps)

    def is_piece_in_motion(self, cell: Position) -> bool:
        """Return True if a piece originating from cell is currently moving."""
        return any(m.src == cell for m in self._motions)

    def start_motion(self, piece: Piece, src: Position, dest: Position) -> None:
        """
        Begin moving piece from src to dest.

        Duration is determined by cell-step count × 1000 ms.
        """
        duration = travel_duration_ms(src, dest)
        piece.state = PieceState.MOVING
        self._motions.append(Motion(
            piece=piece,
            src=src,
            dest=dest,
            arrival_time=self._clock_ms + duration,
        ))

    def get_active_motions(self) -> list[Motion]:
        """Return a read-only view of all currently active motions."""
        return list(self._motions)

    def redirect_motion(self, motion: Motion, new_dest: Position) -> None:
        """
        Shorten an in-flight motion to new_dest.

        Recalculates arrival_time proportionally so the piece keeps its
        current speed — it doesn't suddenly teleport or slow down.
        new_dest must lie on the original path between the piece's current
        position and the original dest.
        """
        old_steps = max(
            abs(motion.dest.row - motion.src.row),
            abs(motion.dest.col - motion.src.col),
        )
        new_steps = max(
            abs(new_dest.row - motion.src.row),
            abs(new_dest.col - motion.src.col),
        )
        if old_steps == 0:
            return
        # Scale arrival_time: start_time + (new_steps/old_steps) * total_duration
        total_duration = old_steps * (CELL_SIZE_PX * 1000 // PIECE_SPEED_PPS)
        start_time = motion.arrival_time - total_duration
        new_duration = new_steps * (CELL_SIZE_PX * 1000 // PIECE_SPEED_PPS)
        motion.dest = new_dest
        motion.arrival_time = start_time + new_duration
        motion.path = compute_path(motion.src, new_dest)

    def start_jump(self, piece: Piece) -> None:
        """
        Begin a jump for piece at its current cell.

        The piece remains logically on its cell for JUMP_DURATION_MS.
        """
        piece.state = PieceState.JUMPING
        self._jumps.append(JumpMotion(
            piece=piece,
            cell=piece.cell,
            landing_time=self._clock_ms + self._jump_duration_ms,
        ))

    def is_on_cooldown(self, piece: Piece) -> bool:
        """Return True if piece is currently in its post-arrival cooldown."""
        return any(c.piece is piece for c in self._cooldowns)

    def advance_time(self, ms: int) -> None:
        """
        Advance the simulated clock by ms milliseconds and resolve all arrivals.
        """
        self._clock_ms += ms
        self._resolve_arrivals()
        self._expire_cooldowns()
        self._expire_jumps()

    # --- Private resolution ---

    def _resolve_arrivals(self) -> None:
        due     = [m for m in self._motions if self._clock_ms >= m.arrival_time]
        pending = [m for m in self._motions if self._clock_ms <  m.arrival_time]
        due.sort(key=lambda m: m.arrival_time)

        for motion in due:
            self._apply_arrival(motion)

        self._motions = pending

    def _start_cooldown(self, piece: Piece, from_time: int) -> None:
        """Put piece into COOLING state for COOLDOWN_MS after from_time."""
        piece.state = PieceState.COOLING
        self._cooldowns.append(CooldownTimer(piece=piece, ready_time=from_time + self._cooldown_ms))

    def _bounce(self, motion: Motion) -> None:
        """Cancel a colliding motion — piece stays at src and enters cooldown."""
        self._start_cooldown(motion.piece, motion.arrival_time)

    def _apply_arrival(self, motion: Motion) -> None:
        """Resolve a single arriving motion atomically."""
        piece = motion.piece

        if piece.state is PieceState.CAPTURED:
            return

        if self._is_captured_by_airborne(motion):
            return

        if self._is_blocked_by_friendly(motion):
            return

        self._land(motion)

    def _is_captured_by_airborne(self, motion: Motion) -> bool:
        """Return True (and apply capture) if an airborne enemy intercepts the arriving piece."""
        jump = self._active_jump_at(motion.dest, motion.arrival_time, motion.piece)
        if jump is None:
            return False
        self._board.remove_piece(motion.src)
        motion.piece.state = PieceState.CAPTURED
        if Piece.is_royal(motion.piece.kind):
            self._on_king_captured()
        return True

    def _is_blocked_by_friendly(self, motion: Motion) -> bool:
        """Return True (and stop piece one cell before dest) if a friendly occupies dest."""
        dest_piece = self._board.piece_at(motion.dest)
        if dest_piece is None or dest_piece.color != motion.piece.color:
            return False
        stop = self._cell_before_dest(motion)
        if stop == motion.src:
            motion.piece.state = PieceState.IDLE
        else:
            self._board.move_piece(motion.src, stop)
            self._start_cooldown(motion.piece, motion.arrival_time)
            if motion.piece.state is not PieceState.COOLING:
                motion.piece.state = PieceState.IDLE
            self._on_piece_arrived(motion.piece)
        return True

    def _cell_before_dest(self, motion: Motion) -> Position:
        """Return the last cell along the path from src to dest before dest itself."""
        dr = motion.dest.row - motion.src.row
        dc = motion.dest.col - motion.src.col
        steps = max(abs(dr), abs(dc))
        if steps <= 1:
            return motion.src
        step_r = dr // steps
        step_c = dc // steps
        return Position(motion.dest.row - step_r, motion.dest.col - step_c)

    def _land(self, motion: Motion) -> None:
        """Place the arriving piece at dest, capture any enemy there, then notify arrival."""
        captured = self._board.piece_at(motion.dest)
        self._board.move_piece(motion.src, motion.dest)
        self._start_cooldown(motion.piece, motion.arrival_time)
        if motion.piece.state is not PieceState.COOLING:
            motion.piece.state = PieceState.IDLE
        self._on_piece_arrived(motion.piece)
        if captured is not None and Piece.is_royal(captured.kind):
            self._on_king_captured()

    def _active_jump_at(self, cell: Position, arrival_time: int, arriving_piece: Piece) -> Optional[JumpMotion]:
        """Return an enemy JumpMotion at cell that is still airborne at arrival_time, or None."""
        return next(
            (j for j in self._jumps
             if j.cell == cell
             and j.piece.color != arriving_piece.color
             and arrival_time <= j.landing_time),
            None,
        )

    def _expire_jumps(self) -> None:
        """Remove jumps whose landing time has passed and reset piece state."""
        active = []
        for j in self._jumps:
            if self._clock_ms >= j.landing_time:
                if j.piece.state is PieceState.JUMPING:
                    j.piece.state = PieceState.IDLE
            else:
                active.append(j)
        self._jumps = active

    def _expire_cooldowns(self) -> None:
        """Reset pieces whose cooldown has expired to IDLE."""
        active = []
        for c in self._cooldowns:
            if self._clock_ms >= c.ready_time:
                if c.piece.state is PieceState.COOLING:
                    c.piece.state = PieceState.IDLE
            else:
                active.append(c)
        self._cooldowns = active
