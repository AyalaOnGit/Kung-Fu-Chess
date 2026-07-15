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
from ui_config import PIECE_SCALE


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

        # Precompute scaled piece size (same for every piece)
        piece_size = max(1, int(round(CELL_SIZE_PX * PIECE_SCALE)))

        # Draw every piece on the board
        for pos, piece in self._board._grid.items():
            animator = self._get_animator(piece)
            
            # Tick animator
            animator.tick(dt_ms)

            # Top-left pixel of this cell (do NOT mutate these)
            cell_x, cell_y = self._cell_to_pixel(pos)
            
            # Get current sprite frame
            try:
                frame_data = animator.get_current_frame()
                sprite = frame_data.image
                
                # Draw sprite onto frame
                # Defensive: ensure sprite is a numpy array with 2/3/4 channels
                if not isinstance(sprite, np.ndarray):
                    sprite = np.array(sprite, dtype=np.uint8)

                if sprite.ndim == 2:
                    # grayscale -> BGR
                    sprite = cv2.cvtColor(sprite, cv2.COLOR_GRAY2BGR)

                if sprite.ndim == 3 and sprite.shape[2] not in (3, 4):
                    # Unexpected number of channels: try to reduce to 3 (BGR)
                    if sprite.shape[2] >= 3:
                        sprite = sprite[:, :, :3]
                    else:
                        # Repeat single channel to make 3 channels
                        sprite = np.repeat(sprite[:, :, :1], 3, axis=2)

                sprite = sprite.astype(np.uint8)

                # Resize sprite to PIECE_SCALE fraction of the cell, preserving aspect ratio
                sh, sw = sprite.shape[:2]
                scale = min(piece_size / float(sw), piece_size / float(sh))
                new_w = max(1, int(round(sw * scale)))
                new_h = max(1, int(round(sh * scale)))
                if new_w != sw or new_h != sh:
                    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
                    sprite = cv2.resize(sprite, (new_w, new_h), interpolation=interp)
                    sh, sw = sprite.shape[:2]

                # Center sprite exactly in the board cell
                px_x = cell_x + (CELL_SIZE_PX - sw) // 2
                px_y = cell_y + (CELL_SIZE_PX - sh) // 2

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
                    
                    src_patch = sprite[src_y1:src_y2, src_x1:src_x2]
                    if sprite.shape[2] == 4:  # BGRA
                        # Blend with alpha channel in a clear, vectorized way
                        alpha = src_patch[:, :, 3].astype(float) / 255.0
                        alpha = alpha[..., np.newaxis]
                        src_rgb = src_patch[:, :, :3].astype(float)
                        # Destination may have 3 or 4 channels; blend into first 3
                        dst_rgb = frame[y1:y2, x1:x2, :3].astype(float)
                        out_rgb = (1.0 - alpha) * dst_rgb + alpha * src_rgb
                        frame[y1:y2, x1:x2, :3] = out_rgb.astype(np.uint8)
                    else:  # BGR (3 channels)
                        # If destination has 4 channels, write only to RGB channels
                        if frame.shape[2] == 4:
                            frame[y1:y2, x1:x2, :3] = src_patch
                        else:
                            frame[y1:y2, x1:x2] = src_patch

                # Draw jump highlight — bright cyan border around the cell
                if piece.state.value == 'jumping':
                    self._draw_jump_highlight(frame, cell_x, cell_y)
                # Draw cooldown highlight — orange border around the cell
                elif piece.state.value == 'cooling':
                    self._draw_cooldown_highlight(frame, cell_x, cell_y)

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

    def _draw_jump_highlight(self, frame: np.ndarray, cell_x: int, cell_y: int) -> None:
        """Draw a glowing cyan border around a jumping piece's cell."""
        margin = 3
        x1 = cell_x + margin
        y1 = cell_y + margin
        x2 = cell_x + CELL_SIZE_PX - margin
        y2 = cell_y + CELL_SIZE_PX - margin
        # Outer glow (thicker, semi-transparent feel via two passes)
        cv2.rectangle(frame, (x1 - 2, y1 - 2), (x2 + 2, y2 + 2), (180, 220, 0, 255), 2)
        # Inner bright cyan border
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 0, 255), 3)

    def _draw_cooldown_highlight(self, frame: np.ndarray, cell_x: int, cell_y: int) -> None:
        """Draw an orange border around a piece that is cooling down."""
        margin = 3
        x1 = cell_x + margin
        y1 = cell_y + margin
        x2 = cell_x + CELL_SIZE_PX - margin
        y2 = cell_y + CELL_SIZE_PX - margin
        # Outer glow
        cv2.rectangle(frame, (x1 - 2, y1 - 2), (x2 + 2, y2 + 2), (0, 100, 200, 255), 2)
        # Inner bright orange border
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 165, 255, 255), 3)
