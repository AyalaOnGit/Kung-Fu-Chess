"""
HUD Renderer: renders sidebar with game information.

Composes board canvas with moves log, score, and captured-piece thumbnails.
"""
from __future__ import annotations
import pathlib
import numpy as np

from vendor.img import Img
from ui_config import (
    SIDEBAR_WIDTH_PX, SIDEBAR_BG_COLOR, SIDEBAR_MARGIN_PX, TEXT_COLOR,
    HUD_FONT_SCALE_HEADER, HUD_FONT_SCALE_SECTION, HUD_FONT_SCALE_LABEL,
    HUD_FONT_SCALE_COLUMN_HEADER, HUD_FONT_SCALE_MOVE,
    MOVES_LOG_VISIBLE_ROWS, MOVES_LOG_ROW_HEIGHT_PX, CAPTURED_THUMB_SIZE_PX,
    GAME_OVER_OVERLAY_COLOR, GAME_OVER_OVERLAY_ALPHA, GAME_OVER_TEXT_COLOR,
    GAME_OVER_TITLE_FONT_SCALE, GAME_OVER_DETAIL_FONT_SCALE, GAME_OVER_LINE_GAP_PX,
    GAME_OVER_PANEL_COLOR, GAME_OVER_PANEL_ALPHA, GAME_OVER_PANEL_BORDER_COLOR,
    GAME_OVER_PANEL_PADDING_X_PX, GAME_OVER_PANEL_PADDING_Y_PX,
    GAME_OVER_RATING_UP_COLOR, GAME_OVER_RATING_DOWN_COLOR,
)
from kungfu_chess.model.piece import Kind, Color
from state.game_events import GameOverInfo

# Kind → folder name prefix (matches assets folder names)
_KIND_CODE = {
    Kind.PAWN: 'P', Kind.KNIGHT: 'N', Kind.BISHOP: 'B',
    Kind.ROOK: 'R', Kind.QUEEN: 'Q', Kind.KING: 'K',
}
_COLOR_CODE = {Color.WHITE: 'W', Color.BLACK: 'B'}


class ThumbnailCache:
    """
    Loads and caches small idle-pose thumbnails for captured-piece display.

    Sole responsibility: given (kind, color), return a ready-to-blit thumbnail.
    """

    def __init__(self, size_px: int = CAPTURED_THUMB_SIZE_PX):
        self._size = size_px
        self._pieces_dir: pathlib.Path | None = None
        self._cache: dict[tuple, np.ndarray] = {}

    def set_pieces_dir(self, path: pathlib.Path) -> None:
        self._pieces_dir = pathlib.Path(path)
        self._cache.clear()

    def get(self, kind: Kind, color: Color) -> np.ndarray | None:
        key = (kind, color)
        if key in self._cache:
            return self._cache[key]
        if self._pieces_dir is None:
            return None

        code = _KIND_CODE[kind] + _COLOR_CODE[color]
        sprite_dir = self._pieces_dir / code / 'states' / 'idle' / 'sprites'
        files = sorted(sprite_dir.glob('*.png'), key=lambda p: int(p.stem)) if sprite_dir.exists() else []
        if not files:
            return None

        try:
            thumb_img = Img().read(files[0])
        except FileNotFoundError:
            return None
        thumb_img.crop_to_content()
        h, w = thumb_img.img.shape[:2]
        scale = self._size / max(h, w)
        thumb_img.resize(max(1, int(w * scale)), max(1, int(h * scale)))

        self._cache[key] = thumb_img.img
        return thumb_img.img


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
                 player_white: str = 'White', player_black: str = 'Black',
                 white_elo: int | None = None, black_elo: int | None = None):
        self._board_width  = board_width
        self._board_height = board_height
        self._player_white = player_white
        self._player_black = player_black
        self._white_elo = white_elo
        self._black_elo = black_elo
        self._white_score  = 0
        self._black_score  = 0
        self._white_captured: list[Kind] = []
        self._black_captured: list[Kind] = []
        self._white_moves: list[str] = []
        self._black_moves: list[str] = []
        self._game_over_info: GameOverInfo | None = None
        self._room_id: str | None = None
        self._network_status: str | None = None
        self._my_role: str | None = None
        self._thumbnails = ThumbnailCache()

    def set_pieces_dir(self, path: pathlib.Path) -> None:
        """Tell HudRenderer where to find piece sprites for thumbnails."""
        self._thumbnails.set_pieces_dir(path)

    def set_player(self, role: str, name: str, elo: int | None) -> None:
        """Update one seat's displayed name/elo -- e.g. when a waiting
        room's second player joins mid-session (see main.py's OpponentJoined
        handling). role is 'white' or 'black'."""
        if role == 'white':
            self._player_white = name
            self._white_elo = elo
        elif role == 'black':
            self._player_black = name
            self._black_elo = elo

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

    def set_game_over(self, info: GameOverInfo | None) -> None:
        """Set (or clear, with None) the game-over dialog's content."""
        self._game_over_info = info

    def set_room_id(self, room_id: str | None) -> None:
        """Networked play only: room id, shown at the top of the screen per
        spec ("written on top of the screen")."""
        self._room_id = room_id

    def set_my_role(self, role: str | None) -> None:
        """Networked play only: which color/role *this* window's local
        player controls. Two networked windows on the same desktop are
        otherwise visually identical (same title, same board) -- this and
        the window title (see main.py) are what let a player tell them
        apart instead of accidentally clicking the wrong window."""
        self._my_role = role

    def set_network_status(self, message: str | None) -> None:
        """Networked play only: transient status line (e.g. an opponent
        disconnect auto-resign countdown). None clears it."""
        self._network_status = message

    def render(self, board_frame: np.ndarray) -> np.ndarray:
        h, w = board_frame.shape[:2]
        channels = board_frame.shape[2] if board_frame.ndim > 2 else 1

        bg = SIDEBAR_BG_COLOR
        if isinstance(bg, (list, tuple)) and len(bg) != channels:
            bg = (*bg, 255) if channels == 4 else tuple(bg[:3])
        sidebar = np.full((h, SIDEBAR_WIDTH_PX, channels), bg, dtype=np.uint8)

        img = Img()
        img.img = np.hstack([board_frame, sidebar])
        img.to_bgra()

        sx = w + SIDEBAR_MARGIN_PX
        sw = SIDEBAR_WIDTH_PX - 2 * SIDEBAR_MARGIN_PX

        y = 18
        if self._my_role or self._room_id or self._network_status:
            y = self._draw_network_header(img, sx, y)
        # ── Black player ──────────────────────────────────────────────
        img.put_text(self._player_label(self._player_black, self._black_elo),
                     sx, y, HUD_FONT_SCALE_HEADER, (200, 200, 255), 2)
        y += 24
        img.put_text(f'Score: {self._black_score}', sx, y, HUD_FONT_SCALE_LABEL, TEXT_COLOR, 1)
        y += 6
        y = self._draw_captured_row(img, sx, y, self._black_captured, Color.WHITE)

        # ── Separator ─────────────────────────────────────────────────
        y += 6
        img.draw_line(sx, y, sx + sw, y, (80, 80, 80), 1)
        y += 12

        # ── Moves log ─────────────────────────────────────────────────
        img.put_text('Moves', sx, y, HUD_FONT_SCALE_SECTION, TEXT_COLOR, 1)
        y += 18
        col_w = sw // 2
        img.put_text(self._player_black[:6], sx,         y, HUD_FONT_SCALE_COLUMN_HEADER, (180, 180, 255), 1)
        img.put_text(self._player_white[:6], sx + col_w, y, HUD_FONT_SCALE_COLUMN_HEADER, (255, 255, 180), 1)
        y += 16
        for i in range(MOVES_LOG_VISIBLE_ROWS):
            row_y = y + i * MOVES_LOG_ROW_HEIGHT_PX
            if i < len(self._black_moves):
                img.put_text(self._black_moves[-(i + 1)], sx,         row_y, HUD_FONT_SCALE_MOVE, TEXT_COLOR, 1)
            if i < len(self._white_moves):
                img.put_text(self._white_moves[-(i + 1)], sx + col_w, row_y, HUD_FONT_SCALE_MOVE, TEXT_COLOR, 1)
        y += MOVES_LOG_VISIBLE_ROWS * MOVES_LOG_ROW_HEIGHT_PX + 6

        # ── Separator ─────────────────────────────────────────────────
        img.draw_line(sx, y, sx + sw, y, (80, 80, 80), 1)
        y += 12

        # ── White player ──────────────────────────────────────────────
        img.put_text(self._player_label(self._player_white, self._white_elo),
                     sx, y, HUD_FONT_SCALE_HEADER, (255, 255, 180), 2)
        y += 24
        img.put_text(f'Score: {self._white_score}', sx, y, HUD_FONT_SCALE_LABEL, TEXT_COLOR, 1)
        y += 6
        self._draw_captured_row(img, sx, y, self._white_captured, Color.BLACK)

        if self._game_over_info is not None:
            self._draw_game_over_overlay(img, w, h)

        return img.img

    @staticmethod
    def _player_label(name: str, elo: int | None) -> str:
        return f'{name} ({elo})' if elo is not None else name

    def _draw_network_header(self, img: Img, sx: int, y: int) -> int:
        """Your role + room id + any transient network status (disconnect
        countdown, etc), drawn at the top of the sidebar. Returns the new y."""
        if self._my_role:
            role_color = (0, 220, 0) if self._my_role == 'viewer' else (255, 255, 255)
            img.put_text(f'You are: {self._my_role.upper()}', sx, y,
                         HUD_FONT_SCALE_HEADER, role_color, 2)
            y += 22
        if self._room_id:
            img.put_text(f'Room: {self._room_id}', sx, y, HUD_FONT_SCALE_LABEL, TEXT_COLOR, 1)
            y += 18
        if self._network_status:
            img.put_text(self._network_status, sx, y, HUD_FONT_SCALE_LABEL, (0, 120, 255), 1)
            y += 18
        y += 6
        img.draw_line(sx, y, sx + SIDEBAR_WIDTH_PX - 2 * SIDEBAR_MARGIN_PX, y, (80, 80, 80), 1)
        y += 12
        return y

    def _draw_captured_row(self, img: Img, sx: int, y: int,
                            captured: list[Kind], piece_color: Color) -> int:
        """
        Draw a row of small piece thumbnails for captured pieces.
        piece_color = the color of the pieces that were captured
        (e.g. black captured white pieces → piece_color=WHITE).
        Returns the new y after the row.
        """
        if not captured:
            return y + CAPTURED_THUMB_SIZE_PX + 4

        row_y = y + 4
        per_row = (SIDEBAR_WIDTH_PX - 2 * SIDEBAR_MARGIN_PX) // (CAPTURED_THUMB_SIZE_PX + 2)
        for i, kind in enumerate(captured):
            if i > 0 and i % per_row == 0:
                row_y += CAPTURED_THUMB_SIZE_PX + 2
            col = sx + (i % per_row) * (CAPTURED_THUMB_SIZE_PX + 2)
            thumb = self._thumbnails.get(kind, piece_color)
            if thumb is not None:
                th, tw = thumb.shape[:2]
                blit_x = col + (CAPTURED_THUMB_SIZE_PX - tw) // 2
                blit_y = row_y + (CAPTURED_THUMB_SIZE_PX - th) // 2
                img.blit(thumb, blit_x, blit_y)
            else:
                # Fallback: letter
                img.put_text(_KIND_CODE[kind], col + 4, row_y + CAPTURED_THUMB_SIZE_PX - 6,
                             HUD_FONT_SCALE_LABEL, TEXT_COLOR, 1)

        rows_used = (len(captured) - 1) // per_row + 1
        return row_y + rows_used * (CAPTURED_THUMB_SIZE_PX + 2)

    def _draw_game_over_overlay(self, img: Img, board_w: int, board_h: int) -> None:
        """Dim the board and draw a centered dialog card: the winner (or
        draw) as a title, then -- once RatingUpdate has arrived -- each
        player's new rating and signed ELO change below it, colored green
        for a gain and red for a loss."""
        img.fill_rect_blend(0, 0, board_w, board_h, GAME_OVER_OVERLAY_COLOR, GAME_OVER_OVERLAY_ALPHA)

        info = self._game_over_info
        lines = [(info.title, GAME_OVER_TITLE_FONT_SCALE, GAME_OVER_TEXT_COLOR)]
        if info.white_label is not None and info.black_label is not None:
            white_color = GAME_OVER_RATING_UP_COLOR if info.white_delta >= 0 else GAME_OVER_RATING_DOWN_COLOR
            black_color = GAME_OVER_RATING_UP_COLOR if info.black_delta >= 0 else GAME_OVER_RATING_DOWN_COLOR
            lines.append((info.white_label, GAME_OVER_DETAIL_FONT_SCALE, white_color))
            lines.append((info.black_label, GAME_OVER_DETAIL_FONT_SCALE, black_color))

        sizes = [Img.text_size(text, scale, 2) for text, scale, _ in lines]
        content_w = max(line_w for line_w, _ in sizes)
        content_h = sum(line_h for _, line_h in sizes) + GAME_OVER_LINE_GAP_PX * (len(lines) - 1)

        panel_w = content_w + 2 * GAME_OVER_PANEL_PADDING_X_PX
        panel_h = content_h + 2 * GAME_OVER_PANEL_PADDING_Y_PX
        panel_x1, panel_y1 = board_w // 2 - panel_w // 2, board_h // 2 - panel_h // 2
        panel_x2, panel_y2 = panel_x1 + panel_w, panel_y1 + panel_h

        img.fill_rect_blend(panel_x1, panel_y1, panel_x2, panel_y2, GAME_OVER_PANEL_COLOR, GAME_OVER_PANEL_ALPHA)
        img.draw_rect(panel_x1, panel_y1, panel_x2, panel_y2, GAME_OVER_PANEL_BORDER_COLOR, 2)

        y = panel_y1 + GAME_OVER_PANEL_PADDING_Y_PX
        for (text, scale, color), (line_w, line_h) in zip(lines, sizes):
            y += line_h
            img.put_text(text, board_w // 2 - line_w // 2, y, scale, color, 2)
            y += GAME_OVER_LINE_GAP_PX
