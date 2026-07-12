from __future__ import annotations
from typing import Callable, Optional
from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece, PieceState
from kungfu_chess.model.position import Position
from kungfu_chess.realtime.motion import Motion, JumpMotion, CooldownTimer, travel_duration_ms
from kungfu_chess.config import JUMP_DURATION_MS, COOLDOWN_MS


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
                 on_piece_arrived: Callable[[Piece], None]):
        """
        :param board:             The logical board to mutate on arrival.
        :param on_king_captured:  Called when a king is captured during arrival resolution.
        :param on_piece_arrived:  Called after a piece lands at its destination.
        """
        self._board             = board
        self._on_king_captured  = on_king_captured
        self._on_piece_arrived  = on_piece_arrived
        self._clock_ms:    int  = 0
        self._motions:     list[Motion]      = []
        self._jumps:       list[JumpMotion]  = []
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

    def start_jump(self, piece: Piece) -> None:
        """
        Begin a jump for piece at its current cell.

        The piece remains logically on its cell for JUMP_DURATION_MS.
        """
        piece.state = PieceState.JUMPING
        self._jumps.append(JumpMotion(
            piece=piece,
            cell=piece.cell,
            landing_time=self._clock_ms + JUMP_DURATION_MS,
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

        # Collision: two pieces arriving at the same dest in the same tick — both bounce back
        dest_counts: dict[Position, int] = {}
        for m in due:
            dest_counts[m.dest] = dest_counts.get(m.dest, 0) + 1

        colliding = {dest for dest, count in dest_counts.items() if count > 1}
        resolved, bounced = [], []
        for m in due:
            (bounced if m.dest in colliding else resolved).append(m)

        for motion in bounced:
            self._bounce(motion)
        for motion in resolved:
            self._apply_arrival(motion)

        self._motions = pending

    def _start_cooldown(self, piece: Piece, from_time: int) -> None:
        """Put piece into COOLING state for COOLDOWN_MS after from_time."""
        piece.state = PieceState.COOLING
        self._cooldowns.append(CooldownTimer(piece=piece, ready_time=from_time + COOLDOWN_MS))

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
        """Return True (and cancel motion) if a friendly piece already occupies dest."""
        dest_piece = self._board.piece_at(motion.dest)
        if dest_piece is not None and dest_piece.color == motion.piece.color:
            motion.piece.state = PieceState.IDLE
            return True
        return False

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
