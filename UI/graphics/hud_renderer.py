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
        self._white_score = 0
        self._black_score = 0
        self._white_moves: list[str] = []
        self._black_moves: list[str] = []
    
    def update_score(self, white_score: int, black_score: int) -> None:
        """Update score display."""
        self._white_score = white_score
        self._black_score = black_score
    
    def set_moves(self, moves: dict[str, list[str]]) -> None:
        """Replace the current displayed move logs."""
        self._white_moves = list(moves.get('white', []))
        self._black_moves = list(moves.get('black', []))
    
    def render(self, board_frame: np.ndarray) -> np.ndarray:
        """
        Compose board and sidebar into one frame.
        
        :param board_frame: the rendered board
        :return: frame with sidebar
        """
        h, w = board_frame.shape[:2]
        channels = board_frame.shape[2] if len(board_frame.shape) > 2 else 1
        
        # Create sidebar: ensure background color matches channel count
        bg = SIDEBAR_BG_COLOR
        if isinstance(bg, (list, tuple)):
            if len(bg) != channels:
                if channels == 4 and len(bg) == 3:
                    bg = (*bg, 255)
                elif channels == 3 and len(bg) == 4:
                    bg = tuple(bg[:3])
                elif channels == 1:
                    # convert RGB/A to grayscale
                    vals = list(bg)
                    avg = int(round(sum(vals) / len(vals)))
                    bg = avg
        sidebar = np.full((h, SIDEBAR_WIDTH_PX, channels), bg, dtype=np.uint8)
        
        # Compose board + sidebar
        if channels == 4:
            result = np.hstack([board_frame, sidebar])
        else:
            result = np.hstack([board_frame, sidebar])
        
        # Draw score header
        header_y = 40
        cv2.putText(result, "Score", (w + 20, header_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, TEXT_COLOR, 2)
        cv2.putText(result, f"Black: {self._black_score}", (w + 20, header_y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, TEXT_COLOR, 1)
        cv2.putText(result, f"White: {self._white_score}", (w + 20, header_y + 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, TEXT_COLOR, 1)

        # Separator line
        cv2.line(result, (w + 10, header_y + 70), (w + SIDEBAR_WIDTH_PX - 10, header_y + 70), TEXT_COLOR, 1)

        # Moves columns
        col_x = w + 20
        col_mid = w + SIDEBAR_WIDTH_PX // 2
        title_y = header_y + 95
        cv2.putText(result, "Black", (col_x, title_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, TEXT_COLOR, 1)
        cv2.putText(result, "White", (col_mid + 10, title_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, TEXT_COLOR, 1)

        black_y = title_y + 25
        white_y = title_y + 25
        max_moves = 10
        for i in range(max_moves):
            if i < len(self._black_moves):
                cv2.putText(result, self._black_moves[-(i + 1)], (col_x, black_y + i * 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, TEXT_COLOR, 1)
            if i < len(self._white_moves):
                cv2.putText(result, self._white_moves[-(i + 1)], (col_mid + 10, white_y + i * 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, TEXT_COLOR, 1)

        return result
