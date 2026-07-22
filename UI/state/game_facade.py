"""
GameFacade: bridges server engine with UI animation and event system.

Responsibilities:
  - Request moves/jumps from the server
  - Predict motion duration; queue animations
  - Detect game events (arrival, capture, promotion, etc.)
  - Publish events to observers
  - Handle cooldowns and motion state
"""
from __future__ import annotations
from typing import Optional, Dict

from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.engine.commands import MoveCommand, JumpCommand
from kungfu_chess.interaction.controller import Controller
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece, PieceState
from kungfu_chess.interaction.board_mapper import BoardMapper
from kungfu_chess.config import JUMP_DURATION_MS

from state.observer import Subject
from state.game_events import (
    MoveAccepted, MoveRejected, PieceArrived, PieceCaptured,
    PieceHalted, Promotion, GameOver, GameEvent
)
from state.motion_tracking import PendingMotionData, pixel_motion_for
from kungfu_chess.observation.snapshot_diff import FrozenSnapshot, diff_snapshots
from animation.motion_predictor import PixelMotion, duration_for_move_ms


class GameFacade:
    """
    High-level game controller for the UI.
    
    • Accepts move requests from user clicks
    • Predicts animation duration based on server constants
    • Tracks pending motions and detects arrivals/captures
    • Publishes events for UI components to subscribe to
    
    Uses Subject for pub/sub; owned by main.py.
    """
    
    def __init__(self, engine: GameEngine, mapper: BoardMapper):
        self._engine = engine
        self._mapper = mapper
        self._controller = Controller(engine, mapper)
        
        # Event system
        self._subject: Subject[GameEvent] = Subject()
        
        # Pending motions: piece.id -> PendingMotionData
        self._pending_motions: Dict[int, PendingMotionData] = {}
        
        # Snapshot for diffing
        self._last_snapshot: Optional[FrozenSnapshot] = None
    
    # --- Event publishing ---
    
    def subscribe(self, callback) -> None:
        """Allow UI components to subscribe to game events."""
        self._subject.subscribe(callback)
    
    # --- User input routing ---
    
    def request_jump(self, x: int, y: int) -> None:
        """
        Route a double-click jump request to the controller.

        :param x: pixel x coordinate
        :param y: pixel y coordinate
        """
        if not self._mapper.in_bounds_px(x, y):
            print(f"[jump] out of bounds: ({x}, {y})")
            return
        pos = self._mapper.pixel_to_position(x, y)
        piece = self._engine.board.piece_at(pos)
        if piece is None:
            print(f"[jump] no piece at {pos}")
            return
        result = self._controller.on_jump(x, y)
        print(f"[jump] {piece.token()} at {pos} → accepted={result.is_accepted if result else 'n/a'} reason={result.reason if result else 'n/a'}")
        if result is None or not result.is_accepted:
            # Rejected (e.g. piece is on cooldown, already moving/jumping, game over) —
            # do NOT queue an animation for a jump that never actually happened.
            if result is not None:
                self._subject.publish(MoveRejected(piece=piece, reason=result.reason))
            return
        # Track the jump as a pending motion so animations resolve correctly
        now = self._engine.clock_ms
        self._pending_motions[piece.id] = PendingMotionData(
            piece=piece,
            src_pos=pos,
            dst_pos=pos,
            is_jump=True,
            motion_start_time_ms=now,
            motion_end_time_ms=now + JUMP_DURATION_MS,
        )

    def request_click(self, x: int, y: int) -> bool:
        """
        Route a mouse click to the controller.

        :return: True if this was a destination click (2nd click, src→dst attempt).
                 False if it was a selection click (1st click) or out-of-bounds.
        """
        result, src, dst = self._controller.on_click(x, y)
        if result is None:
            # First click (selection) — NOT a completed move attempt
            return False
        # Second click (destination) — move was attempted (accepted or rejected)
        command_result, src_pos, dst_pos, piece = result
        if command_result.is_accepted and piece is not None:
            self._subject.publish(MoveAccepted(piece=piece, src_pos=src_pos, dst_pos=dst_pos))
            motion_duration_ms = duration_for_move_ms(src_pos, dst_pos)
            now = self._engine.clock_ms
            self._pending_motions[piece.id] = PendingMotionData(
                piece=piece,
                src_pos=src_pos,
                dst_pos=dst_pos,
                is_jump=False,
                motion_start_time_ms=now,
                motion_end_time_ms=now + motion_duration_ms,
            )
        elif piece is not None:
            self._subject.publish(MoveRejected(piece=piece, reason=command_result.reason))
        return True
    
    # --- Core loop ---
    
    def tick(self, dt_ms: float) -> None:
        """
        Advance one frame: handle pending motions, then call engine.wait().
        
        :param dt_ms: milliseconds elapsed this frame
        """
        # Advance time in engine
        self._engine.wait(int(dt_ms))
        
        # Check for completed motions and publish events
        self._check_motion_completions()
    
    def _check_motion_completions(self) -> None:
        """
        Check if any pending motions have finished.
        If so, diff the board state and publish appropriate events.
        """
        current_time = self._engine.clock_ms
        completed_ids = []

        for piece_id, motion_data in self._pending_motions.items():
            if current_time >= motion_data.motion_end_time_ms:
                completed_ids.append(piece_id)
            elif not motion_data.is_jump and motion_data.piece.state is not PieceState.MOVING:
                # piece.cell only updates on arrival (Board.move_piece), never mid-flight,
                # so a state change away from MOVING is the only way to detect that the
                # server resolved the arrival early (e.g. redirected to a shorter landing
                # cell because the path became blocked). Treat it as completed now, using
                # the piece's real landing cell instead of the originally requested dst.
                actual_pos = motion_data.piece.cell
                if actual_pos != motion_data.dst_pos:
                    motion_data.dst_pos = actual_pos
                    self._subject.publish(PieceHalted(piece=motion_data.piece, halted_at=actual_pos))
                completed_ids.append(piece_id)

        # Remove completed
        for piece_id in completed_ids:
            del self._pending_motions[piece_id]

        # If any motions completed, diff the board
        if completed_ids:
            self._diff_and_publish_events()
    
    def _diff_and_publish_events(self) -> None:
        """
        Take a current snapshot, diff  against the last one, and publish events.
        """
        # Get current snapshot
        current_snapshot = FrozenSnapshot.from_board(
            self._engine.board,
            self._engine.game_over
        )
        
        if self._last_snapshot is None:
            # First snapshot, just record it
            self._last_snapshot = current_snapshot
            return
        
        # Diff
        events = diff_snapshots(self._last_snapshot, current_snapshot, {})
        
        # Publish
        for event_type, event_data in events:
            if event_type == 'piece_arrived':
                piece, pos = event_data
                self._subject.publish(PieceArrived(piece=piece, pos=pos))
            elif event_type == 'piece_captured':
                piece, capturer, pos = event_data
                self._subject.publish(PieceCaptured(piece=piece, capturer=capturer, pos=pos))
            elif event_type == 'promotion':
                piece, old_kind, new_kind = event_data
                self._subject.publish(Promotion(piece=piece, old_kind=old_kind, new_kind=new_kind, pos=piece.cell))
            elif event_type == 'game_over':
                winner, loser = event_data
                self._subject.publish(GameOver(winner=winner, loser=loser))
        
        # Update snapshot
        self._last_snapshot = current_snapshot
    
    # --- Motion prediction ---

    def get_selected_pos(self) -> Optional[Position]:
        """Return the currently selected cell, or None."""
        return self._controller.selected

    def get_cooldown_ratio(self, piece: Piece) -> float:
        """
        Return fraction of cooldown remaining for a piece in COOLING state (1.0=just started, 0.0=done).
        Returns 0.0 if the piece is not cooling.
        """
        return self._engine.get_cooldown_ratio(piece)
    
    def get_pending_motion(self, piece_id: int) -> Optional[tuple[PixelMotion, float]]:
        """
        Get motion data and elapsed time for a piece currently in flight.

        :param piece_id: the piece's id
        :return: (PixelMotion, elapsed_ms) or None if not in flight
        """
        motion_data = self._pending_motions.get(piece_id)
        if not motion_data:
            return None
        return pixel_motion_for(motion_data, self._mapper, self._engine.clock_ms)
