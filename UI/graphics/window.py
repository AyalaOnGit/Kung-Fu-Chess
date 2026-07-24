"""
Non-blocking window management.

Wraps window display, mouse input, and close-detection into a manageable
per-frame loop without blocking. All OpenCV access is delegated to Img;
this module never calls cv2 directly.

Keys:
  +  / =   increase scale by SCALE_STEP
  -        decrease scale by SCALE_STEP
"""
from __future__ import annotations
from typing import Callable, Optional
import numpy as np

from vendor.img import Img, MouseEventType
from vendor.img import cv2 as _default_cv2
from ui_config import SCALE_DEFAULT, SCALE_STEP, SCALE_MIN, SCALE_MAX


class Window:
    """
    Non-blocking window controller.

    Responsibilities:
      - Show one frame per display_frame() call, scaled to current zoom level
      - Route mouse clicks to a callback (coordinates mapped back to logical space)
      - Detect window close
      - Handle +/- keys to resize the display
    """

    def __init__(self, title: str, width: int, height: int, cv2_module=_default_cv2):
        self._title  = title
        self._width  = width
        self._height = height
        self._scale  = SCALE_DEFAULT
        self._window_open = True
        self._cv2 = cv2_module
        self._mouse_callback: Optional[Callable[[MouseEventType, int, int, int, int], None]] = None

    def set_mouse_callback(self, callback: Callable[[MouseEventType, int, int, int, int], None]) -> None:
        """Set the mouse callback; coordinates are mapped back to logical (unscaled) space."""
        self._mouse_callback = callback
        Img.create_window(self._title, cv2_module=self._cv2)
        Img.set_mouse_callback(self._title, self._on_mouse, cv2_module=self._cv2)

    def _on_mouse(self, event: int, x: int, y: int, flags: int, param: None) -> None:
        """Map scaled pixel coords back to logical coords before forwarding."""
        if not self._mouse_callback:
            return
        try:
            mouse_event = MouseEventType(event)
        except ValueError:
            # cv2 delivers every mouse event through this one callback --
            # move, wheel scroll, right/middle-click, drag, etc. -- but
            # MouseEventType only names the 4 this app acts on. Anything
            # else used to crash the whole render loop (ValueError from the
            # Enum constructor, uncaught inside cv2's own callback); ignore
            # it instead, exactly as MouseController already ignores any
            # recognized-but-unhandled event type below.
            return
        lx = int(x / self._scale)
        ly = int(y / self._scale)
        self._mouse_callback(mouse_event, lx, ly, flags, param)

    def display_frame(self, frame: np.ndarray, fps: Optional[float] = None) -> None:
        """
        Display a frame scaled to the current zoom level.

        :param frame: numpy array (height, width, channels in BGR or BGRA)
        :param fps: optional FPS value to display as overlay
        """
        if not self._window_open:
            return

        img = Img()
        img.img = frame.copy()

        if fps is not None:
            img.put_text(f"FPS: {fps:.1f}", 10, 30, 0.7, (255, 255, 255), 2)

        if self._scale != 1.0:
            new_w = max(1, int(img.img.shape[1] * self._scale))
            new_h = max(1, int(img.img.shape[0] * self._scale))
            img.resize(new_w, new_h)

        if not img.show_in_window(self._title, cv2_module=self._cv2):
            self._window_open = False
            return

        key = Img.wait_key(1, cv2_module=self._cv2)
        self._handle_key(key)

        if not Img.is_window_visible(self._title, cv2_module=self._cv2):
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
        Img.destroy_window(self._title, cv2_module=self._cv2)
        self._window_open = False
