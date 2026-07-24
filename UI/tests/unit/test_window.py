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

Every cv2 window-management call goes through Img's injectable `cv2_module`
parameter (see vendor/img.py) -- tests here pass a small hand-written fake
backend (_FakeCv2Backend) instead of ever opening a real OS window or
patching the cv2 import.
"""
import cv2
import numpy as np

from graphics.window import Window
from ui_config import SCALE_MIN, SCALE_MAX
from vendor.img import Img


class _FakeCv2Backend:
    """Records every call it receives; stands in for the real cv2 module
    wherever Img/Window accept an injectable `cv2_module`."""

    class error(Exception):
        pass

    def __init__(self):
        self.calls = []
        self.imshow_raises = None
        self.get_window_property_raises = None
        self.get_window_property_value = 1.0
        self.wait_key_value = -1

    def namedWindow(self, title, flag):
        self.calls.append(('namedWindow', title, flag))

    def imshow(self, title, img):
        self.calls.append(('imshow', title, img.shape))
        if self.imshow_raises is not None:
            raise self.imshow_raises

    def waitKey(self, ms):
        self.calls.append(('waitKey', ms))
        return self.wait_key_value

    def getWindowProperty(self, title, prop):
        self.calls.append(('getWindowProperty', title, prop))
        if self.get_window_property_raises is not None:
            raise self.get_window_property_raises
        return self.get_window_property_value

    def destroyWindow(self, title):
        self.calls.append(('destroyWindow', title))

    def setMouseCallback(self, title, callback):
        self.calls.append(('setMouseCallback', title, callback))


def test_create_window_uses_autosize_not_normal():
    """WINDOW_NORMAL is what let the window be resized independently of the
    image in the first place -- must never come back."""
    backend = _FakeCv2Backend()
    Img.create_window('test-title', cv2_module=backend)
    assert backend.calls == [('namedWindow', 'test-title', cv2.WINDOW_AUTOSIZE)]


def test_show_in_window_also_uses_autosize():
    img = Img()
    img.img = np.zeros((10, 10, 4), dtype='uint8')
    backend = _FakeCv2Backend()
    img.show_in_window('test-title', cv2_module=backend)
    assert backend.calls[0] == ('namedWindow', 'test-title', cv2.WINDOW_AUTOSIZE)


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


def test_set_mouse_callback_creates_the_window_and_registers_the_handler():
    backend = _FakeCv2Backend()
    window = Window('test', 800, 600, cv2_module=backend)
    calls = []

    window.set_mouse_callback(lambda *a: calls.append(a))

    assert backend.calls == [
        ('namedWindow', 'test', cv2.WINDOW_AUTOSIZE),
        ('setMouseCallback', 'test', window._on_mouse),
    ]
    assert window._mouse_callback is not None


def test_on_mouse_with_no_callback_registered_is_a_no_op():
    window = Window('test', 800, 600)
    window._on_mouse(event=0, x=1, y=1, flags=0, param=None)  # must not raise


def test_display_frame_shows_the_frame_and_polls_a_key_when_window_stays_open():
    backend = _FakeCv2Backend()
    window = Window('test', 800, 600, cv2_module=backend)
    frame = np.zeros((600, 800, 4), dtype=np.uint8)

    window.display_frame(frame, fps=60.0)

    assert ('imshow', 'test', frame.shape) in backend.calls
    assert ('waitKey', 1) in backend.calls
    assert window.is_open() is True


def test_display_frame_is_a_no_op_once_the_window_is_already_closed():
    backend = _FakeCv2Backend()
    window = Window('test', 800, 600, cv2_module=backend)
    window._window_open = False
    frame = np.zeros((600, 800, 4), dtype=np.uint8)

    window.display_frame(frame)

    assert backend.calls == []


def test_display_frame_marks_the_window_closed_when_show_in_window_fails():
    backend = _FakeCv2Backend()
    backend.imshow_raises = backend.error('boom')
    window = Window('test', 800, 600, cv2_module=backend)
    frame = np.zeros((600, 800, 4), dtype=np.uint8)

    window.display_frame(frame)

    assert window.is_open() is False


def test_display_frame_marks_the_window_closed_once_no_longer_visible():
    backend = _FakeCv2Backend()
    backend.get_window_property_value = -1.0
    window = Window('test', 800, 600, cv2_module=backend)
    frame = np.zeros((600, 800, 4), dtype=np.uint8)

    window.display_frame(frame)

    assert window.is_open() is False


def test_display_frame_scales_the_image_to_the_current_zoom_level():
    backend = _FakeCv2Backend()
    window = Window('test', 800, 600, cv2_module=backend)
    window._scale = 2.0
    frame = np.zeros((50, 100, 4), dtype=np.uint8)  # (height=50, width=100)

    window.display_frame(frame)

    imshow_call = next(c for c in backend.calls if c[0] == 'imshow')
    assert imshow_call[2][:2] == (100, 200)  # (height, width) doubled


def test_display_frame_applies_the_key_it_reads_via_handle_key():
    backend = _FakeCv2Backend()
    backend.wait_key_value = ord('+')
    window = Window('test', 800, 600, cv2_module=backend)
    frame = np.zeros((10, 10, 4), dtype=np.uint8)

    window.display_frame(frame)

    assert window.scale == 1.1


def test_handle_key_plus_or_equals_increases_scale_clamped_to_max():
    window = Window('test', 800, 600)
    window._handle_key(ord('='))
    assert window.scale == 1.1

    window._scale = SCALE_MAX
    window._handle_key(ord('+'))
    assert window.scale == SCALE_MAX  # clamped, doesn't overshoot


def test_handle_key_minus_decreases_scale_clamped_to_min():
    window = Window('test', 800, 600)
    window._handle_key(ord('-'))
    assert window.scale == 0.9

    window._scale = SCALE_MIN
    window._handle_key(ord('-'))
    assert window.scale == SCALE_MIN  # clamped, doesn't undershoot


def test_handle_key_ignores_unrelated_keys():
    window = Window('test', 800, 600)
    window._handle_key(ord('a'))
    assert window.scale == 1.0


def test_close_destroys_the_window_and_marks_it_closed():
    backend = _FakeCv2Backend()
    window = Window('test', 800, 600, cv2_module=backend)

    window.close()

    assert backend.calls == [('destroyWindow', 'test')]
    assert window.is_open() is False


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
