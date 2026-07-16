"""
Mouse click handler: converts cv2 mouse events to game commands.

Double-click = two clicks on the SAME cell within DOUBLE_CLICK_MS → jump.
After a completed move (src→dst), the timer resets so the next click
on any cell starts fresh and cannot accidentally trigger a jump.
"""
from __future__ import annotations
from typing import Callable, Optional
import time
import cv2

DOUBLE_CLICK_MS     = 300   # ms between two clicks to count as double-click
DOUBLE_CLICK_RADIUS = 20    # max pixel distance between the two clicks


class MouseController:
    """
    Routes cv2 mouse callbacks to click_handler / jump_handler.

    State machine:
      IDLE                → LEFT_DOWN on A            → SELECTED(A, t)
      SELECTED(A, t)      → LEFT_DOWN on A within 300ms → JUMP(A) → IDLE
      SELECTED(A, t)      → LEFT_DOWN on B (different)  → MOVE(A→B) → IDLE
      SELECTED(A, t)      → LEFT_DOWN on A after 300ms  → SELECTED(A, t2)
    """

    def __init__(self,
                 click_handler: Callable[[int, int], bool],
                 jump_handler: Optional[Callable[[int, int], None]] = None):
        self._click_handler = click_handler
        self._jump_handler  = jump_handler
        self._last_time_ms: float = 0.0
        self._last_x: int = -9999
        self._last_y: int = -9999

    def on_mouse_event(self, event: int, x: int, y: int, flags: int, param) -> None:
        # Native OS double-click (Windows fires this reliably)
        if event == cv2.EVENT_LBUTTONDBLCLK:
            self._reset()
            if self._jump_handler:
                self._jump_handler(x, y)
            return

        if event != cv2.EVENT_LBUTTONDOWN:
            return

        now_ms = time.monotonic() * 1000.0
        dt     = now_ms - self._last_time_ms
        dx     = abs(x - self._last_x)
        dy     = abs(y - self._last_y)

        same_spot = dx <= DOUBLE_CLICK_RADIUS and dy <= DOUBLE_CLICK_RADIUS
        fast      = dt <= DOUBLE_CLICK_MS

        if same_spot and fast:
            # Two rapid clicks on same spot → jump
            self._reset()
            if self._jump_handler:
                self._jump_handler(x, y)
        else:
            is_dest_click = self._click_handler(x, y)
            if is_dest_click:
                # Was a src→dst click — reset fully, next click starts fresh
                self._reset()
            else:
                # Was a selection click (1st click) — record NOW for double-click detection
                self._last_time_ms = now_ms
                self._last_x = x
                self._last_y = y

    def _reset(self) -> None:
        self._last_time_ms = 0.0
        self._last_x = -9999
        self._last_y = -9999
