"""
Unit tests for UI/vendor/img.py's Img wrapper -- every direct cv2 access in
the UI goes through this class. Real image-manipulation methods (resize,
crop, blit, guards) run against plain numpy arrays with real cv2 calls, since
those need no GUI/display and are cheap; anything that would touch an actual
OS window (show/show_in_window/wait_key/is_window_visible/destroy_window/
set_mouse_callback) is exercised via Img's injectable `cv2_module` parameter,
passing a small hand-written fake backend (the same convention
test_window.py uses) instead of ever opening a real window.
"""
import cv2
import numpy as np
import pytest

from vendor.img import Img


def _bgr(h, w):
    return np.zeros((h, w, 3), dtype=np.uint8)


def _bgra(h, w):
    return np.zeros((h, w, 4), dtype=np.uint8)


class _FakeCv2Backend:
    """Records every call it receives; stands in for the real cv2 module
    wherever Img accepts an injectable `cv2_module`."""

    class error(Exception):
        pass

    def __init__(self):
        self.calls = []
        self.raises = None
        self.get_window_property_value = 1.0
        self.wait_key_value = 0

    def namedWindow(self, title, flag):
        self.calls.append(('namedWindow', title, flag))

    def imshow(self, title, img):
        self.calls.append(('imshow', title))
        if self.raises is not None:
            raise self.raises

    def waitKey(self, ms):
        self.calls.append(('waitKey', ms))
        return self.wait_key_value

    def getWindowProperty(self, title, prop):
        self.calls.append(('getWindowProperty', title, prop))
        if self.raises is not None:
            raise self.raises
        return self.get_window_property_value

    def destroyWindow(self, title):
        self.calls.append(('destroyWindow', title))
        if self.raises is not None:
            raise self.raises

    def setMouseCallback(self, title, callback):
        self.calls.append(('setMouseCallback', title, callback))

    def destroyAllWindows(self):
        self.calls.append(('destroyAllWindows',))


# --- read() ---

def test_read_raises_when_the_file_does_not_exist(tmp_path):
    with pytest.raises(FileNotFoundError):
        Img().read(tmp_path / 'missing.png')


def test_read_resizes_when_a_size_is_given(tmp_path):
    path = tmp_path / 'blank.png'
    cv2.imwrite(str(path), _bgr(20, 10))

    img = Img().read(path, size=(5, 8))

    assert img.img.shape[:2] == (8, 5)  # (height, width)


# --- resize() ---

def test_resize_raises_when_image_not_loaded():
    with pytest.raises(ValueError):
        Img().resize(10, 10)


def test_resize_keep_aspect_shrinks_to_fit_the_longer_side():
    img = Img()
    img.img = _bgr(100, 200)  # h=100, w=200 -- landscape

    img.resize(50, 50, keep_aspect=True)

    h, w = img.img.shape[:2]
    assert max(h, w) == 50
    assert (w, h) == (50, 25)  # aspect preserved


# --- to_bgra() ---

def test_to_bgra_is_a_no_op_when_image_not_loaded():
    assert Img().to_bgra().img is None


def test_to_bgra_converts_grayscale_to_4_channels():
    img = Img()
    img.img = np.zeros((10, 10), dtype=np.uint8)
    img.to_bgra()
    assert img.img.shape == (10, 10, 4)


def test_to_bgra_converts_bgr_to_4_channels():
    img = Img()
    img.img = _bgr(10, 10)
    img.to_bgra()
    assert img.img.shape == (10, 10, 4)


def test_to_bgra_leaves_existing_bgra_untouched():
    img = Img()
    img.img = _bgra(10, 10)
    img.to_bgra()
    assert img.img.shape == (10, 10, 4)


# --- crop_to_content() ---

def test_crop_to_content_returns_unchanged_when_fully_transparent():
    img = Img()
    img.img = _bgra(10, 10)  # alpha channel all zero -- nothing "found"
    img.crop_to_content()
    assert img.img.shape == (10, 10, 4)


def test_crop_to_content_crops_to_the_opaque_region():
    img = Img()
    arr = _bgra(20, 20)
    arr[5:10, 5:10, 3] = 255  # opaque square
    img.img = arr
    img.crop_to_content(padding=0)
    assert img.img.shape[:2] == (5, 5)


# --- blit() ---

def test_blit_raises_when_target_not_loaded():
    with pytest.raises(ValueError):
        Img().blit(_bgra(5, 5), 0, 0)


def test_blit_raises_when_sprite_not_loaded():
    img = Img()
    img.img = _bgra(5, 5)
    with pytest.raises(ValueError):
        img.blit(Img(), 0, 0)  # Img wrapper whose .img is still None


def test_blit_entirely_out_of_bounds_is_a_no_op():
    img = Img()
    img.img = _bgra(5, 5)
    original = img.img.copy()

    img.blit(_bgra(3, 3), 100, 100)  # nowhere near the canvas

    assert np.array_equal(img.img, original)


def test_blit_3_channel_sprite_overwrites_pixels_directly():
    img = Img()
    img.img = _bgra(5, 5)
    sprite = np.full((2, 2, 3), 200, dtype=np.uint8)

    img.blit(sprite, 0, 0)

    assert (img.img[0:2, 0:2, :3] == 200).all()


def test_blit_4_channel_sprite_alpha_blends():
    img = Img()
    img.img = _bgra(5, 5)
    sprite = np.full((2, 2, 4), 255, dtype=np.uint8)  # fully opaque white

    img.blit(sprite, 0, 0)

    assert (img.img[0:2, 0:2, :3] == 255).all()


# --- fill_rect_blend / put_text / draw_rect / draw_line guards ---

def test_fill_rect_blend_raises_when_not_loaded():
    with pytest.raises(ValueError):
        Img().fill_rect_blend(0, 0, 1, 1, (0, 0, 0), 0.5)


def test_fill_rect_blend_blends_a_rectangle():
    img = Img()
    img.img = _bgr(10, 10)
    img.fill_rect_blend(0, 0, 5, 5, (100, 100, 100), 1.0)
    assert (img.img[0:5, 0:5] == 100).all()


def test_put_text_raises_when_not_loaded():
    with pytest.raises(ValueError):
        Img().put_text('hi', 0, 0, 1.0)


def test_draw_rect_raises_when_not_loaded():
    with pytest.raises(ValueError):
        Img().draw_rect(0, 0, 1, 1, (0, 0, 0))


def test_draw_line_raises_when_not_loaded():
    with pytest.raises(ValueError):
        Img().draw_line(0, 0, 1, 1, (0, 0, 0))


def test_text_size_returns_positive_width_and_height():
    w, h = Img.text_size('hi', 1.0)
    assert w > 0 and h > 0


# --- show() ---

def test_show_raises_when_not_loaded():
    with pytest.raises(ValueError):
        Img().show()


def test_show_displays_waits_and_destroys_all_windows():
    img = Img()
    img.img = _bgr(5, 5)
    backend = _FakeCv2Backend()

    img.show(cv2_module=backend)

    assert backend.calls == [('imshow', 'Image'), ('waitKey', 0), ('destroyAllWindows',)]


# --- window management ---

def test_set_mouse_callback_delegates_to_cv2():
    def callback(*a):
        pass
    backend = _FakeCv2Backend()

    Img.set_mouse_callback('title', callback, cv2_module=backend)

    assert backend.calls == [('setMouseCallback', 'title', callback)]


def test_show_in_window_raises_when_not_loaded():
    with pytest.raises(ValueError):
        Img().show_in_window('title')


def test_show_in_window_returns_false_on_cv2_error():
    img = Img()
    img.img = _bgr(5, 5)
    backend = _FakeCv2Backend()
    backend.raises = backend.error('boom')

    assert img.show_in_window('title', cv2_module=backend) is False


def test_wait_key_masks_to_8_bits():
    backend = _FakeCv2Backend()
    backend.wait_key_value = 0x1FF41

    assert Img.wait_key(1, cv2_module=backend) == 0x41


def test_is_window_visible_true_when_property_non_negative():
    backend = _FakeCv2Backend()
    backend.get_window_property_value = 1.0

    assert Img.is_window_visible('title', cv2_module=backend) is True


def test_is_window_visible_false_on_cv2_error():
    backend = _FakeCv2Backend()
    backend.raises = backend.error('boom')

    assert Img.is_window_visible('title', cv2_module=backend) is False


def test_destroy_window_calls_cv2_destroy():
    backend = _FakeCv2Backend()

    Img.destroy_window('title', cv2_module=backend)

    assert backend.calls == [('destroyWindow', 'title')]


def test_destroy_window_swallows_cv2_error():
    backend = _FakeCv2Backend()
    backend.raises = backend.error('boom')

    Img.destroy_window('title', cv2_module=backend)  # must not raise


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
