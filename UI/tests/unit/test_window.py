"""
Unit tests for UI/graphics/window.py's mouse-coordinate handling and
UI/vendor/img.py's window creation flags.

Regression coverage for a real bug: the window used to be created with
cv2.WINDOW_NORMAL (resizable), and Window._on_mouse only corrected clicks
for the app's own +/- zoom, never for the window having been resized by the
user/OS (e.g. maximized) independently of the displayed image. On this
project's OpenCV build, cv2.getWindowImageRect() -- tried as a fix -- was
confirmed (empirically, against a real window) to report bogus, non-
uniformly-scaled dimensions, which made click mapping *worse* (almost
nothing was clickable) rather than better. The actual fix is simpler: make
the window non-resizable (WINDOW_AUTOSIZE) so there's nothing to mis-measure
in the first place; zoom still works because AUTOSIZE follows imshow()'s
image size automatically, and the app's own +/- keys resize the image
before every imshow() call.
"""
import sys
import pathlib
from unittest.mock import patch

ui_dir = pathlib.Path(__file__).parent.parent.parent
if str(ui_dir) not in sys.path:
    sys.path.insert(0, str(ui_dir))

import server_bridge  # noqa: F401

import cv2

from graphics.window import Window
from vendor.img import Img


def test_create_window_uses_autosize_not_normal():
    """WINDOW_NORMAL is what let the window be resized independently of the
    image in the first place -- must never come back."""
    with patch('vendor.img.cv2.namedWindow') as named_window:
        Img.create_window('test-title')
    named_window.assert_called_once_with('test-title', cv2.WINDOW_AUTOSIZE)


def test_show_in_window_also_uses_autosize():
    import numpy as np
    img = Img()
    img.img = np.zeros((10, 10, 4), dtype='uint8')
    with patch('vendor.img.cv2.namedWindow') as named_window, patch('vendor.img.cv2.imshow'):
        img.show_in_window('test-title')
    named_window.assert_called_once_with('test-title', cv2.WINDOW_AUTOSIZE)


def test_mouse_coords_pass_through_unscaled_at_default_zoom():
    window = Window('test', 1122, 828)
    received = []
    # Set the callback directly rather than via set_mouse_callback() --
    # that calls Img.create_window(), which would open a real OS window as
    # a side effect of running the test suite.
    window._mouse_callback = lambda event, x, y, flags, param: received.append((x, y))

    window._on_mouse(event=0, x=561, y=414, flags=0, param=None)

    assert received == [(561, 414)]


def test_mouse_coords_are_divided_by_the_apps_own_zoom_factor():
    window = Window('test', 1122, 828)
    window._scale = 2.0
    received = []
    window._mouse_callback = lambda event, x, y, flags, param: received.append((x, y))

    window._on_mouse(event=0, x=200, y=100, flags=0, param=None)

    assert received == [(100, 50)]


def test_unrecognized_cv2_event_codes_are_ignored_not_raised():
    """Regression test: cv2 delivers every mouse event through this one
    callback (move, wheel scroll, right/middle-click, drag...), but
    MouseEventType only names 4 of cv2's ~12 event codes. Constructing the
    Enum from an unnamed code (e.g. 10 == cv2.EVENT_MOUSEWHEEL, from
    scrolling over the board) used to raise ValueError uncaught inside cv2's
    callback and crash the whole render loop."""
    window = Window('test', 1122, 828)
    received = []
    window._mouse_callback = lambda event, x, y, flags, param: received.append((x, y))

    for unrecognized_event_code in (10, 11, 2, 5, 6, 8, 9):  # wheel, hwheel, right/middle click...
        window._on_mouse(event=unrecognized_event_code, x=100, y=100, flags=0, param=None)  # must not raise

    assert received == []  # never forwarded to the app's callback


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
