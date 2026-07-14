"""
HUD Renderer: renders sidebar with game information.

Composes board canvas with moves log and score panels.
"""
from __future__ import annotations
from typing import Optional
import numpy as np
import cv2

from ui_config import SIDEBAR_WIDTH_PX, SIDEBAR_BG_COLOR, TEXT_COLOR


class HudRenderer:
    """
    Composes the game HUD: board + sidebar with panels.
    
    Responsibilities:
      - Take a board frame
      - Render moves log panel
      - Render score panel
      - Compose into a wider canvas with sidebar
    """
    
    def __init__(self, board_width: int, board_height: int):
        self._board_width = board_width
        self._board_height = board_height
        self._sidebar_text = "Game Info"
        self._score_text = "White: 0  Black: 0"
        self._moves_log = []
    
    def update_score(self, white_score: int, black_score: int) -> None:
        """Update score display."""
        self._score_text = f"White: {white_score}  Black: {black_score}"
    
    def add_move(self, move_text: str) -> None:
        """Add a move to the log."""
        self._moves_log.append(move_text)
    
    def render(self, board_frame: np.ndarray) -> np.ndarray:
        """
        Compose board and sidebar into one frame.
        
        :param board_frame: the rendered board
        :return: frame with sidebar
        """
        h, w = board_frame.shape[:2]
        channels = board_frame.shape[2] if len(board_frame.shape) > 2 else 1
        
        # Create sidebar
        sidebar = np.full((h, SIDEBAR_WIDTH_PX, channels), SIDEBAR_BG_COLOR, dtype=np.uint8)
        
        # Compose board + sidebar
        if channels == 4:
            result = np.hstack([board_frame, sidebar])
        else:
            result = np.hstack([board_frame, sidebar])
        
        # Add text labels
        y_pos = 30
        cv2.putText(result, "Moves:", (w + 20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, TEXT_COLOR, 1)
        y_pos += 30
        
        for move in self._moves_log[-10:]:  # Show last 10 moves
            cv2.putText(result, str(move), (w + 20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5, TEXT_COLOR, 1)
            y_pos += 25
        
        # Score
        cv2.putText(result, self._score_text, (w + 20, h - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, TEXT_COLOR, 1)
        
        return result
