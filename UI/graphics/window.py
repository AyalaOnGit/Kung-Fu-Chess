"""
Non-blocking cv2 window management.

Wraps cv2.imshow() + cv2.setMouseCallback() + cv2.waitKey(1) + close-detect
into a manageable per-frame loop without blocking.
"""
from __future__ import annotations
from typing import Callable, Optional
import cv2
import numpy as np


class Window:
    """
    Non-blocking OpenCV window controller.
    
    Responsibilities:
      - Show one frame per is_open() call (via display_frame)
      - Route mouse clicks to a callback
      - Detect window close
      - Update window title with optional FPS overlay
    """
    
    def __init__(self, title: str, width: int, height: int):
        self._title = title
        self._width = width
        self._height = height
        self._window_open = True
        self._mouse_callback: Optional[Callable[[int, int, int, int, int], None]] = None
        
    def set_mouse_callback(self, callback: Callable[[int, int, int, int, int], None]) -> None:
        """Set the mouse callback to route cv2 clicks."""
        self._mouse_callback = callback
        cv2.namedWindow(self._title)
        cv2.setMouseCallback(self._title, self._on_mouse)
    
    def _on_mouse(self, event: int, x: int, y: int, flags: int, param: None) -> None:
        """Internal cv2 mouse callback adapter."""
        if self._mouse_callback:
            self._mouse_callback(event, x, y, flags, param)
    
    def display_frame(self, frame: np.ndarray, fps: Optional[float] = None) -> None:
        """
        Display a frame and check for window close.
        
        :param frame: numpy array (height, width, channels in BGR or BGRA)
        :param fps: optional FPS value to display as overlay
        """
        if not self._window_open:
            return
        
        # Make a copy to avoid modifying the original
        display_frame = frame.copy()
        
        # Add FPS overlay if provided
        if fps is not None:
            fps_text = f"FPS: {fps:.1f}"
            # White text with black background for readability
            cv2.putText(display_frame, fps_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Ensure window exists and display
        try:
            cv2.namedWindow(self._title)
            cv2.imshow(self._title, display_frame)
        except cv2.error:
            self._window_open = False
            return
        
        # Process events: 1ms timeout so we don't block
        key = cv2.waitKey(1)
        
        # Check if window was closed
        # (getWindowProperty returns -1 if window closed)
        prop = cv2.getWindowProperty(self._title, cv2.WND_PROP_VISIBLE)
        if prop < 0:
            self._window_open = False
    
    def is_open(self) -> bool:
        """Return True if window is still open."""
        return self._window_open
    
    def close(self) -> None:
        """Close the window."""
        try:
            cv2.destroyWindow(self._title)
        except cv2.error:
            pass
        self._window_open = False
