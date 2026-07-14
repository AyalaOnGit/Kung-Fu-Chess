"""
Mouse click handler: converts cv2 mouse events to server's Controller.

No rendering or game knowledge—just adapts click coordinates into
the server's command interface.
"""
from __future__ import annotations
from typing import Optional
import cv2
from kungfu_chess.input.controller import Controller


class MouseController:
    """
    Routes cv2 mouse callbacks into the server's Controller.
    
    Responsibilities:
      - Adapt cv2 mouse callback format to Controller.on_click
      - Filter for left-click events only
      - Ignore right-click, movement, etc.
    """
    
    def __init__(self, server_controller: Controller):
        self._controller = server_controller
    
    def on_mouse_event(self, event: int, x: int, y: int, flags: int, param: None) -> None:
        """
        cv2 mouse callback adapter.
        
        :param event: cv2 mouse event type
        :param x: pixel x coordinate
        :param y: pixel y coordinate
        :param flags: cv2 flags (shift, ctrl, etc.)
        :param param: user-provided param (unused)
        """
        # Only process left click
        if event == cv2.EVENT_LBUTTONDOWN:
            self._controller.on_click(x, y)
