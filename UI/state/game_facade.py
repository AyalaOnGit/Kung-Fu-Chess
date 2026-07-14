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
from dataclasses import dataclass
from enum import Enum

from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.engine.commands import MoveCommand, JumpCommand
from kungfu_chess.input.controller import Controller
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece, PieceState
from kungfu_chess.input.board_mapper import BoardMapper
from kungfu_chess.config import CELL_SIZE_PX, PIECE_SPEED_PPS, JUMP_DURATION_MS

from state.observer import Subject
from state.game_events import (
    MoveAccepted, MoveRejected, PieceArrived, PieceCaptured,
    PieceHalted, Promotion, GameOver, GameEvent
)
from state.snapshot_diff import FrozenSnapshot, diff_snapshots
from animation.motion_predictor import PixelMotion


@dataclass
class PendingMotionData:
    """Tracks a piece in motion."""
    piece: Piece
    src_pos: Position
    dst_pos: Position
    is_jump: bool
    motion_end_time_ms: float  # clock_ms when motion will finish


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
    
    def request_click(self, x: int, y: int) -> None:
        """
        Route a mouse click to the controller.
        
        :param x: pixel x coordinate
        :param y: pixel y coordinate
        """
        self._controller.on_click(x, y)
    
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
    
    def get_pending_motion(self, piece_id: int) -> Optional[PixelMotion]:
        """
        Get motion data for a piece currently in flight.
        
        :param piece_id: the piece's id
        :return: PixelMotion or None if not in flight
        """
        motion_data = self._pending_motions.get(piece_id)
        if not motion_data:
            return None
        
        # Calculate pixel coordinates
        src_px_x = motion_data.src_pos.col * CELL_SIZE_PX + CELL_SIZE_PX // 2
        src_px_y = motion_data.src_pos.row * CELL_SIZE_PX + CELL_SIZE_PX // 2
        dst_px_x = motion_data.dst_pos.col * CELL_SIZE_PX + CELL_SIZE_PX // 2
        dst_px_y = motion_data.dst_pos.row * CELL_SIZE_PX + CELL_SIZE_PX // 2
        
        if motion_data.is_jump:
            duration_ms = JUMP_DURATION_MS
        else:
            # Calculate based on distance
            distance_cells = abs(motion_data.dst_pos.col - motion_data.src_pos.col)
            if distance_cells == 0:
                distance_cells = abs(motion_data.dst_pos.row - motion_data.src_pos.row)
            
            distance_px = distance_cells * CELL_SIZE_PX
            duration_ms = (distance_px / PIECE_SPEED_PPS) * 1000
        
        return PixelMotion(
            src_px=(src_px_x, src_px_y),
            dst_px=(dst_px_x, dst_px_y),
            duration_ms=duration_ms
        )
