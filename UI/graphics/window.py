"""
Non-blocking cv2 window management.

Wraps cv2.imshow() + cv2.setMouseCallback() + cv2.waitKey(1) + close-detect
into a manageable per-frame loop without blocking.

Keys:
  +  / =   increase scale by SCALE_STEP
  -        decrease scale by SCALE_STEP
"""
from __future__ import annotations
from typing import Callable, Optional
import cv2
import numpy as np

from ui_config import SCALE_DEFAULT, SCALE_STEP, SCALE_MIN, SCALE_MAX


class Window:
    """
    Non-blocking OpenCV window controller.

    Responsibilities:
      - Show one frame per display_frame() call, scaled to current zoom level
      - Route mouse clicks to a callback (coordinates mapped back to logical space)
      - Detect window close
      - Handle +/- keys to resize the display
    """

    def __init__(self, title: str, width: int, height: int):
        self._title  = title
        self._width  = width
        self._height = height
        self._scale  = SCALE_DEFAULT
        self._window_open = True
        self._mouse_callback: Optional[Callable[[int, int, int, int, int], None]] = None

    def set_mouse_callback(self, callback: Callable[[int, int, int, int, int], None]) -> None:
        """Set the mouse callback; coordinates are mapped back to logical (unscaled) space."""
        self._mouse_callback = callback
        cv2.namedWindow(self._title, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(self._title, self._on_mouse)

    def _on_mouse(self, event: int, x: int, y: int, flags: int, param: None) -> None:
        """Map scaled pixel coords back to logical coords before forwarding."""
        if self._mouse_callback:
            lx = int(x / self._scale)
            ly = int(y / self._scale)
            self._mouse_callback(event, lx, ly, flags, param)

    def display_frame(self, frame: np.ndarray, fps: Optional[float] = None) -> None:
        """
        Display a frame scaled to the current zoom level.

        :param frame: numpy array (height, width, channels in BGR or BGRA)
        :param fps: optional FPS value to display as overlay
        """
        if not self._window_open:
            return

        display = frame.copy()

        if fps is not None:
            from vendor.img import Img
            img = Img()
            img.img = display
            img.put_text(f"FPS: {fps:.1f}", 10, 30, 0.7, (255, 255, 255), 2)

        # Scale the frame for display
        if self._scale != 1.0:
            new_w = max(1, int(display.shape[1] * self._scale))
            new_h = max(1, int(display.shape[0] * self._scale))
            interp = cv2.INTER_LINEAR if self._scale > 1.0 else cv2.INTER_AREA
            display = cv2.resize(display, (new_w, new_h), interpolation=interp)

        try:
            cv2.namedWindow(self._title, cv2.WINDOW_NORMAL)
            cv2.imshow(self._title, display)
        except cv2.error:
            self._window_open = False
            return

        key = cv2.waitKey(1) & 0xFF
        self._handle_key(key)

        if cv2.getWindowProperty(self._title, cv2.WND_PROP_VISIBLE) < 0:
            self._window_open = False

    def _handle_key(self, key: int) -> None:
        """Handle +/- keys for zoom."""
        if key in (ord('+'), ord('=')):
            self._scale = min(SCALE_MAX, round(self._scale + SCALE_STEP, 1))
        elif key == ord('-'):
            self._scale = max(SCALE_MIN, round(self._scale - SCALE_STEP, 1))

    @property
    def scale(self) -> float:
        """Current display scale factor."""
        return self._scale

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
