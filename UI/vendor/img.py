from __future__ import annotations

import pathlib
from enum import IntEnum

import cv2
import numpy as np


class MouseEventType(IntEnum):
    """Backend-agnostic mouse event codes — the only place cv2's event
    constants are referenced outside this module."""
    MOVE        = cv2.EVENT_MOUSEMOVE
    LEFT_DOWN   = cv2.EVENT_LBUTTONDOWN
    LEFT_UP     = cv2.EVENT_LBUTTONUP
    LEFT_DBLCLK = cv2.EVENT_LBUTTONDBLCLK


class Img:
    """
    Thin wrapper that owns every direct OpenCV call in the UI.

    All rendering (loading, resizing, colorspace conversion, compositing,
    drawing, and window display) must go through this class — no other
    module should import cv2 directly.
    """

    def __init__(self):
        self.img = None

    def read(self, path: str | pathlib.Path,
             size: tuple[int, int] | None = None,
             keep_aspect: bool = False,
             interpolation: int = cv2.INTER_AREA) -> "Img":
        """
        Load `path` into self.img and **optionally resize**.

        Parameters
        ----------
        path : str | Path
            Image file to load.
        size : (width, height) | None
            Target size in pixels.  If None, keep original.
        keep_aspect : bool
            • False  → resize exactly to `size`
            • True   → shrink so the *longer* side fits `size` while
                       preserving aspect ratio (no cropping).
        interpolation : OpenCV flag
            E.g.  `cv2.INTER_AREA` for shrink, `cv2.INTER_LINEAR` for enlarge.

        Returns
        -------
        Img
            `self`, so you can chain:  `sprite = Img().read("foo.png", (64,64))`
        """
        path = str(path)
        self.img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if self.img is None:
            raise FileNotFoundError(f"Cannot load image: {path}")

        if size is not None:
            self.resize(*size, keep_aspect=keep_aspect, interpolation=interpolation)

        return self

    def resize(self, width: int, height: int, keep_aspect: bool = False,
               interpolation: int | None = None) -> "Img":
        """Resize self.img to (width, height), optionally preserving aspect ratio."""
        if self.img is None:
            raise ValueError("Image not loaded.")
        h, w = self.img.shape[:2]
        if keep_aspect:
            scale = min(width / w, height / h)
            width, height = int(w * scale), int(h * scale)
        if interpolation is None:
            interpolation = cv2.INTER_AREA if (width, height) < (w, h) else cv2.INTER_LINEAR
        width = max(1, width)
        height = max(1, height)
        self.img = cv2.resize(self.img, (width, height), interpolation=interpolation)
        return self

    def to_bgra(self) -> "Img":
        """Ensure self.img has 4 channels (grayscale/BGR are converted; BGRA passes through)."""
        if self.img is None:
            return self
        if self.img.ndim == 2:
            self.img = cv2.cvtColor(self.img, cv2.COLOR_GRAY2BGRA)
        elif self.img.shape[2] == 3:
            self.img = cv2.cvtColor(self.img, cv2.COLOR_BGR2BGRA)
        return self

    def crop_to_content(self, alpha_threshold: int = 10, padding: int = 2) -> "Img":
        """Crop self.img to the tight bounding box of its non-transparent pixels."""
        if self.img is None or self.img.ndim < 3 or self.img.shape[2] < 4:
            return self
        alpha = self.img[:, :, 3]
        rows = np.any(alpha > alpha_threshold, axis=1)
        cols = np.any(alpha > alpha_threshold, axis=0)
        if not rows.any():
            return self
        rmin, rmax = np.where(rows)[0][[0, -1]]
        cmin, cmax = np.where(cols)[0][[0, -1]]
        rmin = max(0, rmin - padding)
        rmax = min(self.img.shape[0] - 1, rmax + padding)
        cmin = max(0, cmin - padding)
        cmax = min(self.img.shape[1] - 1, cmax + padding)
        self.img = self.img[rmin:rmax + 1, cmin:cmax + 1]
        return self

    def blit(self, sprite: "Img | np.ndarray", x: int, y: int) -> None:
        """
        Alpha-composite `sprite` onto self.img at (x, y), clipped to bounds.

        This is the single canonical compositing routine — sprites, HUD
        thumbnails, and overlays should all go through this instead of
        reimplementing the alpha-blend math.
        """
        if self.img is None:
            raise ValueError("Image not loaded.")
        sprite_arr = sprite.img if isinstance(sprite, Img) else sprite
        if sprite_arr is None:
            raise ValueError("Sprite image not loaded.")

        sh, sw = sprite_arr.shape[:2]
        H, W = self.img.shape[:2]
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(W, x + sw), min(H, y + sh)
        if x1 >= x2 or y1 >= y2:
            return

        src = sprite_arr[y1 - y:y2 - y, x1 - x:x2 - x]
        if src.shape[2] == 4:
            alpha = src[:, :, 3:4].astype(float) / 255.0
            dst = self.img[y1:y2, x1:x2, :3].astype(float)
            self.img[y1:y2, x1:x2, :3] = ((1 - alpha) * dst + alpha * src[:, :, :3]).astype(np.uint8)
        else:
            self.img[y1:y2, x1:x2, :3] = src[:, :, :3]

    def fill_rect_blend(self, x1: int, y1: int, x2: int, y2: int,
                         color: tuple, alpha: float) -> "Img":
        """Alpha-blend a filled rectangle into self.img (e.g. selection highlight)."""
        if self.img is None:
            raise ValueError("Image not loaded.")
        overlay = self.img.copy()
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
        cv2.addWeighted(overlay, alpha, self.img, 1 - alpha, 0, self.img)
        return self

    def put_text(self, txt, x, y, font_size, color=(255, 255, 255, 255), thickness=1):
        if self.img is None:
            raise ValueError("Image not loaded.")
        cv2.putText(self.img, txt, (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX, font_size,
                    color, thickness, cv2.LINE_AA)

    @staticmethod
    def text_size(txt: str, font_size: float, thickness: int = 1) -> tuple[int, int]:
        """(width, height) txt would occupy via put_text, in pixels --
        for centering text without needing an actual image loaded."""
        (w, h), baseline = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, font_size, thickness)
        return w, h + baseline

    def draw_rect(self, x1: int, y1: int, x2: int, y2: int,
                   color: tuple, thickness: int = 1) -> "Img":
        """Draw a rectangle on self.img."""
        if self.img is None:
            raise ValueError("Image not loaded.")
        cv2.rectangle(self.img, (x1, y1), (x2, y2), color, thickness)
        return self

    def draw_line(self, x1: int, y1: int, x2: int, y2: int,
                  color: tuple, thickness: int = 1) -> "Img":
        """Draw a line on self.img."""
        if self.img is None:
            raise ValueError("Image not loaded.")
        cv2.line(self.img, (x1, y1), (x2, y2), color, thickness)
        return self

    def show(self, cv2_module=cv2):
        if self.img is None:
            raise ValueError("Image not loaded.")
        cv2_module.imshow("Image", self.img)
        cv2_module.waitKey(0)
        cv2_module.destroyAllWindows()

    # --- Window management (used by graphics.window.Window) ---
    #
    # Every method below takes an injectable `cv2_module` (defaulting to the
    # real cv2), so tests can pass a small hand-written fake backend instead
    # of patching the cv2 import -- avoids ever opening a real OS window
    # during the test suite.

    @staticmethod
    def create_window(title: str, cv2_module=cv2) -> None:
        # WINDOW_AUTOSIZE (not WINDOW_NORMAL): the window always exactly
        # matches whatever image imshow() last gave it, and the user can't
        # drag its border to some other size. Mouse coordinates from cv2
        # are only ever reported correctly in image-pixel space when that
        # holds -- letting the window be resized independently of the
        # image (WINDOW_NORMAL) broke click-to-cell mapping, and this
        # build's cv2.getWindowImageRect() (tried as a fix) turned out to
        # report bogus, non-uniformly-scaled dimensions on this backend,
        # making it worse rather than better. Zoom is still available via
        # the app's own +/- keys (graphics.window.Window._handle_key),
        # which resize the *image* before each imshow() -- AUTOSIZE follows
        # that resize automatically.
        cv2_module.namedWindow(title, cv2.WINDOW_AUTOSIZE)

    @staticmethod
    def set_mouse_callback(title: str, callback, cv2_module=cv2) -> None:
        cv2_module.setMouseCallback(title, callback)

    def show_in_window(self, title: str, cv2_module=cv2) -> bool:
        """
        Display self.img in the named window (creates it if needed).

        :return: True on success, False if the underlying window backend
                 failed to display the frame (e.g. window was closed).
        """
        if self.img is None:
            raise ValueError("Image not loaded.")
        try:
            cv2_module.namedWindow(title, cv2.WINDOW_AUTOSIZE)
            cv2_module.imshow(title, self.img)
            return True
        except cv2_module.error:
            return False

    @staticmethod
    def wait_key(delay_ms: int, cv2_module=cv2) -> int:
        return cv2_module.waitKey(delay_ms) & 0xFF

    @staticmethod
    def is_window_visible(title: str, cv2_module=cv2) -> bool:
        try:
            return cv2_module.getWindowProperty(title, cv2.WND_PROP_VISIBLE) >= 0
        except cv2_module.error:
            return False

    @staticmethod
    def destroy_window(title: str, cv2_module=cv2) -> None:
        try:
            cv2_module.destroyWindow(title)
        except cv2_module.error:
            pass
