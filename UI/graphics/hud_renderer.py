"""
HUD Renderer: renders sidebar with game information.

Composes board canvas with moves log, score, and captured-piece thumbnails.
"""
from __future__ import annotations
import pathlib
import numpy as np
import cv2

from vendor.img import Img
from ui_config import SIDEBAR_WIDTH_PX, SIDEBAR_BG_COLOR, TEXT_COLOR
from kungfu_chess.model.piece import Kind, Color

# Thumbnail size for captured pieces (px)
_THUMB = 28
# Pieces dir — set once by main via HudRenderer.set_pieces_dir()
_PIECES_DIR: pathlib.Path | None = None

# Kind → folder name prefix (matches assets folder names)
_KIND_CODE = {
    Kind.PAWN: 'P', Kind.KNIGHT: 'N', Kind.BISHOP: 'B',
    Kind.ROOK: 'R', Kind.QUEEN: 'Q', Kind.KING: 'K',
}
_COLOR_CODE = {Color.WHITE: 'W', Color.BLACK: 'B'}

# Simple LRU-style cache: (kind, color) -> thumbnail ndarray
_thumb_cache: dict[tuple, np.ndarray] = {}


def _load_thumb(kind: Kind, color: Color) -> np.ndarray | None:
    key = (kind, color)
    if key in _thumb_cache:
        return _thumb_cache[key]
    if _PIECES_DIR is None:
        return None
    code = _KIND_CODE[kind] + _COLOR_CODE[color]
    sprite_dir = _PIECES_DIR / code / 'states' / 'idle' / 'sprites'
    files = sorted(sprite_dir.glob('*.png'), key=lambda p: int(p.stem)) if sprite_dir.exists() else []
    if not files:
        return None
    img = cv2.imread(str(files[0]), cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    # Crop to content
    if img.ndim == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3]
        rows = np.any(alpha > 10, axis=1)
        cols = np.any(alpha > 10, axis=0)
        if rows.any():
            r0, r1 = np.where(rows)[0][[0, -1]]
            c0, c1 = np.where(cols)[0][[0, -1]]
            img = img[r0:r1+1, c0:c1+1]
    # Resize to thumbnail
    h, w = img.shape[:2]
    scale = _THUMB / max(h, w)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    thumb = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    _thumb_cache[key] = thumb
    return thumb


def _blit(frame: np.ndarray, sprite: np.ndarray, x: int, y: int) -> None:
    """Alpha-composite sprite onto frame at (x, y)."""
    sh, sw = sprite.shape[:2]
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(frame.shape[1], x + sw), min(frame.shape[0], y + sh)
    if x1 >= x2 or y1 >= y2:
        return
    src = sprite[y1-y:y2-y, x1-x:x2-x]
    if sprite.shape[2] == 4:
        a = src[:, :, 3:4].astype(float) / 255.0
        frame[y1:y2, x1:x2, :3] = (
            (1 - a) * frame[y1:y2, x1:x2, :3].astype(float)
            + a * src[:, :, :3].astype(float)
        ).astype(np.uint8)
    else:
        frame[y1:y2, x1:x2, :3] = src[:, :, :3]


class HudRenderer:
    """
    Composes the game HUD: board + sidebar.

    Layout (top → bottom in sidebar):
      ┌─────────────────┐
      │  BLACK name      │
      │  score  ♟♟♟...  │  ← captured by black (white pieces taken)
      ├─────────────────┤
      │  Moves log       │
      │  black | white   │
      ├─────────────────┤
      │  WHITE name      │
      │  score  ♙♙♙...  │  ← captured by white (black pieces taken)
      └─────────────────┘
    """

    def __init__(self, board_width: int, board_height: int,
                 player_white: str = 'White', player_black: str = 'Black'):
        self._board_width  = board_width
        self._board_height = board_height
        self._player_white = player_white
        self._player_black = player_black
        self._white_score  = 0
        self._black_score  = 0
        self._white_captured: list[Kind] = []
        self._black_captured: list[Kind] = []
        self._white_moves: list[str] = []
        self._black_moves: list[str] = []

    @staticmethod
    def set_pieces_dir(path: pathlib.Path) -> None:
        """Tell HudRenderer where to find piece sprites for thumbnails."""
        global _PIECES_DIR
        _PIECES_DIR = pathlib.Path(path)

    def update_score(self, white_score: int, black_score: int,
                     white_captured: list[Kind] | None = None,
                     black_captured: list[Kind] | None = None) -> None:
        self._white_score    = white_score
        self._black_score    = black_score
        self._white_captured = list(white_captured or [])
        self._black_captured = list(black_captured or [])

    def set_moves(self, moves: dict[str, list[str]]) -> None:
        self._white_moves = list(moves.get('white', []))
        self._black_moves = list(moves.get('black', []))

    def render(self, board_frame: np.ndarray) -> np.ndarray:
        h, w = board_frame.shape[:2]
        channels = board_frame.shape[2] if board_frame.ndim > 2 else 1

        bg = SIDEBAR_BG_COLOR
        if isinstance(bg, (list, tuple)) and len(bg) != channels:
            bg = (*bg, 255) if channels == 4 else tuple(bg[:3])
        sidebar = np.full((h, SIDEBAR_WIDTH_PX, channels), bg, dtype=np.uint8)
        frame = np.hstack([board_frame, sidebar])
        if frame.shape[2] == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)

        img = Img(); img.img = frame
        sx = w + 14   # sidebar left margin
        sw = SIDEBAR_WIDTH_PX - 28

        y = 18
        # ── Black player ──────────────────────────────────────────────
        img.put_text(self._player_black, sx, y, 0.65, (200, 200, 255), 2)
        y += 24
        img.put_text(f'Score: {self._black_score}', sx, y, 0.5, TEXT_COLOR, 1)
        y += 6
        y = self._draw_captured_row(frame, img, sx, y, self._black_captured, Color.WHITE)

        # ── Separator ─────────────────────────────────────────────────
        y += 6
        img.draw_line(sx, y, sx + sw, y, (80, 80, 80), 1)
        y += 12

        # ── Moves log ─────────────────────────────────────────────────
        img.put_text('Moves', sx, y, 0.55, TEXT_COLOR, 1)
        y += 18
        col_w = sw // 2
        img.put_text(self._player_black[:6],  sx,          y, 0.45, (180, 180, 255), 1)
        img.put_text(self._player_white[:6],  sx + col_w,  y, 0.45, (255, 255, 180), 1)
        y += 16
        for i in range(10):
            if i < len(self._black_moves):
                img.put_text(self._black_moves[-(i+1)], sx,         y + i*18, 0.4, TEXT_COLOR, 1)
            if i < len(self._white_moves):
                img.put_text(self._white_moves[-(i+1)], sx+col_w,   y + i*18, 0.4, TEXT_COLOR, 1)
        y += 10 * 18 + 6

        # ── Separator ─────────────────────────────────────────────────
        img.draw_line(sx, y, sx + sw, y, (80, 80, 80), 1)
        y += 12

        # ── White player ──────────────────────────────────────────────
        img.put_text(self._player_white, sx, y, 0.65, (255, 255, 180), 2)
        y += 24
        img.put_text(f'Score: {self._white_score}', sx, y, 0.5, TEXT_COLOR, 1)
        y += 6
        self._draw_captured_row(frame, img, sx, y, self._white_captured, Color.BLACK)

        return frame

    def _draw_captured_row(self, frame: np.ndarray, img: Img,
                            sx: int, y: int,
                            captured: list[Kind], piece_color: Color) -> int:
        """
        Draw a row of small piece thumbnails for captured pieces.
        piece_color = the color of the pieces that were captured
        (e.g. black captured white pieces → piece_color=WHITE).
        Returns the new y after the row.
        """
        if not captured:
            return y + _THUMB + 4

        x = sx
        row_y = y + 4
        per_row = (SIDEBAR_WIDTH_PX - 28) // (_THUMB + 2)
        for i, kind in enumerate(captured):
            if i > 0 and i % per_row == 0:
                row_y += _THUMB + 2
            col = sx + (i % per_row) * (_THUMB + 2)
            thumb = _load_thumb(kind, piece_color)
            if thumb is not None:
                # Center thumb in its slot
                th, tw = thumb.shape[:2]
                blit_x = col + (_THUMB - tw) // 2
                blit_y = row_y + (_THUMB - th) // 2
                _blit(frame, thumb, blit_x, blit_y)
            else:
                # Fallback: letter
                img.put_text(_KIND_CODE[kind], col + 4, row_y + _THUMB - 6, 0.5, TEXT_COLOR, 1)

        rows_used = (len(captured) - 1) // per_row + 1
        return row_y + rows_used * (_THUMB + 2)
