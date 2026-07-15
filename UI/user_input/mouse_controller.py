"""
Mouse click handler: converts cv2 mouse events to server's Controller.

No rendering or game knowledge—just adapts click coordinates into
the server's command interface.

Double-click detection: two LEFT_BUTTON_DOWN events within DOUBLE_CLICK_MS
milliseconds and DOUBLE_CLICK_RADIUS pixels of each other trigger a jump.
"""
from __future__ import annotations
from typing import Callable, Optional
import time
import cv2

# Maximum gap between two clicks to count as a double-click (ms)
DOUBLE_CLICK_MS = 300
# Maximum pixel distance between the two clicks
DOUBLE_CLICK_RADIUS = 20


class MouseController:
    """
    Routes cv2 mouse callbacks into the server's Controller.

    Responsibilities:
      - Adapt cv2 mouse callback format to Controller.on_click / on_jump
      - Detect double-click (same position, within time threshold) → jump
      - Single left-click → normal move
      - Ignore right-click, movement, etc.
    """

    def __init__(
        self,
        click_handler: Callable[[int, int], None],
        jump_handler: Optional[Callable[[int, int], None]] = None,
    ):
        self._click_handler = click_handler
        self._jump_handler = jump_handler

        # State for double-click detection
        self._last_click_time_ms: float = 0.0
        self._last_click_x: int = 0
        self._last_click_y: int = 0

    def on_mouse_event(self, event: int, x: int, y: int, flags: int, param: None) -> None:
        """
        cv2 mouse callback adapter.

        :param event: cv2 mouse event type
        :param x: pixel x coordinate
        :param y: pixel y coordinate
        :param flags: cv2 flags (shift, ctrl, etc.)
        :param param: user-provided param (unused)
        """
        if event == cv2.EVENT_LBUTTONDBLCLK:
            # cv2 on Windows fires a native double-click event — use it directly
            self._last_click_time_ms = 0.0  # reset so next click is fresh
            print(f"[mouse] native double-click at ({x}, {y})")
            if self._jump_handler is not None:
                self._jump_handler(x, y)
            return

        if event != cv2.EVENT_LBUTTONDOWN:
            return

        now_ms = time.monotonic() * 1000.0
        dt_ms = now_ms - self._last_click_time_ms
        dx = abs(x - self._last_click_x)
        dy = abs(y - self._last_click_y)

        is_double = (
            dt_ms <= DOUBLE_CLICK_MS
            and dx <= DOUBLE_CLICK_RADIUS
            and dy <= DOUBLE_CLICK_RADIUS
        )

        if is_double:
            # Reset so a triple-click doesn't fire a second jump
            self._last_click_time_ms = 0.0
            print(f"[mouse] double-click at ({x}, {y}) dt={dt_ms:.0f}ms")
            if self._jump_handler is not None:
                self._jump_handler(x, y)
        else:
            # Record this click and forward as a normal move click
            self._last_click_time_ms = now_ms
            self._last_click_x = x
            self._last_click_y = y
            self._click_handler(x, y)
