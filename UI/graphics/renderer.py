"""
Board renderer: draws the board and all pieces with animations.

Composes board, pieces at their animated positions, and overlays (selection, halt flash).
"""
from __future__ import annotations
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
import numpy as np
import cv2

from vendor.img import Img
from graphics.sprite_loader import SpriteLoader
from animation.piece_animator import PieceAnimator, PieceAnimatorState
from animation.motion_predictor import PixelMotion, interpolate_pixel
from kungfu_chess.config import CELL_SIZE_PX
from kungfu_chess.model.position import Position
from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece


class BoardRenderer:
    """
    Renders the board and all pieces to a frame.
    
    Responsibilities:
      - Draw the board background
      - Draw each piece at its position
      - Draw selection highlight overlay
      - Advance animation state for all pieces
    """
    
    def __init__(self, board: Board, sprite_loader: SpriteLoader, board_img_path: str):
        """
        Initialize the renderer.
        
        :param board: the game Board instance
        :param sprite_loader: SpriteLoader for sprite frames
        :param board_img_path: path to board.png
        """
        self._board = board
        self._sprite_loader = sprite_loader
        
        # Load board image
        try:
            self._board_img = Img().read(board_img_path)
            self._frame_height, self._frame_width = self._board_img.img.shape[:2]
        except Exception as e:
            print(f"Warning: Could not load board image: {e}")
            # Create blank board
            self._frame_width = board.width * CELL_SIZE_PX
            self._frame_height = board.height * CELL_SIZE_PX
            blank = np.ones((self._frame_height, self._frame_width, 3), dtype=np.uint8) * 200
            self._board_img = Img()
            self._board_img.img = cv2.cvtColor(blank, cv2.COLOR_BGR2BGRA)
        
        # Piece animators
        self._animators: Dict[int, PieceAnimator] = {}
        
        # Selection state
        self._selected_pos: Optional[Position] = None
    
    def set_selection(self, pos: Optional[Position]) -> None:
        """Set which cell (if any) is selected."""
        self._selected_pos = pos
    
    def _get_animator(self, piece: Piece) -> PieceAnimator:
        """Get or create animator for a piece."""
        if piece.id not in self._animators:
            self._animators[piece.id] = PieceAnimator(
                piece=piece,
                sprite_loader=self._sprite_loader
            )
        return self._animators[piece.id]
    
    def _cell_to_pixel(self, pos: Position) -> Tuple[int, int]:
        """Convert board cell to pixel coords (top-left of cell)."""
        x = pos.col * CELL_SIZE_PX
        y = pos.row * CELL_SIZE_PX
        return (x, y)
    
    def render(self, dt_ms: float) -> np.ndarray:
        """
        Render one frame.
        
        :param dt_ms: time delta since last frame
        :return: rendered frame as numpy array (height, width, channels)
        """
        # Start with board image
        frame = self._board_img.img.copy()
        
        # Draw every piece on the board
        for pos, piece in self._board._grid.items():
            animator = self._get_animator(piece)
            
            # Tick animator
            animator.tick(dt_ms)
            
            # Get pixel position
            px_x, px_y = self._cell_to_pixel(pos)
            
            # Get current sprite frame
            try:
                frame_data = animator.get_current_frame()
                sprite = frame_data.image
                
                # Draw sprite onto frame
                sh, sw = sprite.shape[:2]
                
                # Clamp to frame bounds
                x1 = max(0, px_x)
                y1 = max(0, px_y)
                x2 = min(frame.shape[1], px_x + sw)
                y2 = min(frame.shape[0], px_y + sh)
                
                if x1 < x2 and y1 < y2:
                    src_x1 = x1 - px_x
                    src_y1 = y1 - px_y
                    src_x2 = src_x1 + (x2 - x1)
                    src_y2 = src_y1 + (y2 - y1)
                    
                    if sprite.shape[2] == 4:  # BGRA
                        # Blend with alpha
                        alpha = sprite[src_y1:src_y2, src_x1:src_x2, 3].astype(float) / 255.0
                        for c in range(3):
                            frame[y1:y2, x1:x2, c] = (
                                (1 - alpha[:, :, np.newaxis] if len(alpha.shape) == 2 else (1 - alpha)) * 
                                frame[y1:y2, x1:x2, c] +
                                alpha[:, :, np.newaxis] * sprite[src_y1:src_y2, src_x1:src_x2, c]
                                if len(alpha.shape) > 1 else
                                (1 - alpha) * frame[y1:y2, x1:x2, c] + alpha * sprite[src_y1:src_y2, src_x1:src_x2, c]
                            )
                    else:  # BGR
                        frame[y1:y2, x1:x2] = sprite[src_y1:src_y2, src_x1:src_x2]
            except Exception as e:
                print(f"Error drawing piece: {e}")
        
        # Draw selection highlight if any
        if self._selected_pos:
            px_x, px_y = self._cell_to_pixel(self._selected_pos)
            cv2.rectangle(frame, (px_x, px_y), 
                         (px_x + CELL_SIZE_PX, px_y + CELL_SIZE_PX),
                         (200, 255, 200), 3)
        
        # Ensure we return BGRA
        if frame.shape[2] == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
        elif frame.shape[2] != 4:
            print(f"Warning: frame has {frame.shape[2]} channels")
        
        return frame
