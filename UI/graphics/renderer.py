"""
Board renderer: draws the board and all pieces with animations.
"""
from __future__ import annotations
from typing import Optional, Dict, TYPE_CHECKING
import numpy as np
import cv2

from vendor.img import Img
from graphics.sprite_loader import SpriteLoader
from animation.piece_animator import PieceAnimator, PieceAnimatorState
from animation.motion_predictor import interpolate_pixel
from kungfu_chess.config import CELL_SIZE_PX
from kungfu_chess.model.position import Position
from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece, PieceState
from kungfu_chess.input.board_mapper import BoardMapper
from ui_config import PIECE_SCALE

if TYPE_CHECKING:
    from state.game_facade import GameFacade

_SEL_COLOR = (80, 200, 80, 180)
_COOL_BG   = (30, 30, 30, 200)
_COOL_FG   = (0, 140, 255, 255)
_BAR_H     = 6
_BAR_MARGIN = 4


class BoardRenderer:

    def __init__(self, board: Board, sprite_loader: SpriteLoader,
                 board_img_path: str, facade: 'GameFacade',
                 mapper: BoardMapper):
        self._board         = board
        self._sprite_loader = sprite_loader
        self._facade        = facade
        self._mapper        = mapper

        try:
            self._board_img = Img().read(board_img_path)
        except Exception as e:
            print(f"Warning: Could not load board image: {e}")
            blank = np.ones((board.height * CELL_SIZE_PX,
                             board.width  * CELL_SIZE_PX, 4), dtype=np.uint8) * 200
            self._board_img = Img()
            self._board_img.img = blank

        self._animators: Dict[int, PieceAnimator] = {}
        self._selected_pos: Optional[Position] = None

    def set_selection(self, pos: Optional[Position]) -> None:
        self._selected_pos = pos

    def _get_animator(self, piece: Piece) -> PieceAnimator:
        if piece.id not in self._animators:
            self._animators[piece.id] = PieceAnimator(
                piece=piece, sprite_loader=self._sprite_loader)
        return self._animators[piece.id]

    @staticmethod
    def _piece_state_to_anim(state: PieceState) -> PieceAnimatorState:
        return {
            PieceState.MOVING:  PieceAnimatorState.MOVING,
            PieceState.JUMPING: PieceAnimatorState.JUMPING,
            PieceState.COOLING: PieceAnimatorState.SHORT_REST,
        }.get(state, PieceAnimatorState.IDLE)

    def render(self, dt_ms: float) -> np.ndarray:
        frame = self._board_img.img.copy()
        if frame.shape[2] == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)

        static_pieces: list[tuple] = []
        moving_pieces: list[tuple] = []

        for pos, piece in self._board._grid.items():
            animator = self._get_animator(piece)
            desired  = self._piece_state_to_anim(piece.state)
            if animator.state != desired:
                animator.set_state(desired)
            animator.tick(dt_ms)

            cw, ch = self._mapper.cell_size(pos)
            pending = self._facade.get_pending_motion(piece.id)
            if pending is not None:
                pixel_motion, elapsed_ms = pending
                cx, cy = interpolate_pixel(pixel_motion, elapsed_ms)
                moving_pieces.append((piece, cx - cw // 2, cy - ch // 2, cw, ch))
            else:
                cell_x, cell_y = self._mapper.position_to_pixel(pos)
                static_pieces.append((piece, cell_x, cell_y, cw, ch))

        if self._selected_pos:
            self._draw_selection(frame, self._selected_pos)

        for piece, cx, cy, cw, ch in static_pieces:
            self._draw_piece(frame, piece, cx, cy, cw, ch)
        for piece, cx, cy, cw, ch in moving_pieces:
            self._draw_piece(frame, piece, cx, cy, cw, ch)

        return frame

    def _draw_selection(self, frame: np.ndarray, pos: Position) -> None:
        x, y   = self._mapper.position_to_pixel(pos)
        cw, ch = self._mapper.cell_size(pos)
        overlay = frame.copy()
        cv2.rectangle(overlay, (x + 2, y + 2), (x + cw - 2, y + ch - 2), _SEL_COLOR, -1)
        cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, frame)
        fi = Img(); fi.img = frame
        fi.draw_rect(x + 2, y + 2, x + cw - 2, y + ch - 2, (100, 255, 100, 255), 2)

    def _draw_piece(self, frame: np.ndarray, piece: Piece,
                    cell_x: int, cell_y: int, cell_w: int, cell_h: int) -> None:
        animator   = self._get_animator(piece)
        piece_size = max(1, int(round(min(cell_w, cell_h) * PIECE_SCALE)))
        try:
            sprite = animator.get_current_frame().image
            if not isinstance(sprite, np.ndarray):
                sprite = np.array(sprite, dtype=np.uint8)
            if sprite.ndim == 2:
                sprite = cv2.cvtColor(sprite, cv2.COLOR_GRAY2BGRA)
            elif sprite.shape[2] == 3:
                sprite = cv2.cvtColor(sprite, cv2.COLOR_BGR2BGRA)
            sprite = sprite.astype(np.uint8)

            sh, sw = sprite.shape[:2]
            scale  = min(piece_size / float(sw), piece_size / float(sh))
            new_w  = max(1, int(round(sw * scale)))
            new_h  = max(1, int(round(sh * scale)))
            if new_w != sw or new_h != sh:
                interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
                sprite = cv2.resize(sprite, (new_w, new_h), interpolation=interp)
                sh, sw = sprite.shape[:2]

            px_x = cell_x + (cell_w - sw) // 2
            px_y = cell_y + (cell_h - sh) // 2
            self._blit_sprite(frame, sprite, px_x, px_y)

            if piece.state is PieceState.JUMPING:
                self._draw_jump_ring(frame, cell_x, cell_y, cell_w, cell_h)
            elif piece.state is PieceState.COOLING:
                self._draw_cooldown_bar(frame, piece, cell_x, cell_y, cell_w, cell_h)

        except Exception as e:
            print(f"Error drawing piece {piece.token()}: {e}")

    @staticmethod
    def _blit_sprite(frame: np.ndarray, sprite: np.ndarray,
                     px_x: int, px_y: int) -> None:
        sh, sw = sprite.shape[:2]
        x1 = max(0, px_x);       y1 = max(0, px_y)
        x2 = min(frame.shape[1], px_x + sw)
        y2 = min(frame.shape[0], px_y + sh)
        if x1 >= x2 or y1 >= y2:
            return
        src   = sprite[y1 - px_y: y2 - px_y, x1 - px_x: x2 - px_x]
        alpha = src[:, :, 3:4].astype(float) / 255.0
        dst   = frame[y1:y2, x1:x2, :3].astype(float)
        frame[y1:y2, x1:x2, :3] = ((1 - alpha) * dst + alpha * src[:, :, :3]).astype(np.uint8)

    def _draw_jump_ring(self, frame: np.ndarray,
                        cell_x: int, cell_y: int, cell_w: int, cell_h: int) -> None:
        fi = Img(); fi.img = frame
        m = 4
        fi.draw_rect(cell_x + m, cell_y + m,
                     cell_x + cell_w - m, cell_y + cell_h - m,
                     (255, 220, 0, 255), 3)

    def _draw_cooldown_bar(self, frame: np.ndarray, piece: Piece,
                           cell_x: int, cell_y: int, cell_w: int, cell_h: int) -> None:
        ratio = self._facade.get_cooldown_ratio(piece)
        if ratio <= 0.0:
            return
        x1 = cell_x + _BAR_MARGIN
        x2 = cell_x + cell_w - _BAR_MARGIN
        y2 = cell_y + cell_h - _BAR_MARGIN
        y1 = y2 - _BAR_H
        fi = Img(); fi.img = frame
        fi.draw_rect(x1, y1, x2, y2, _COOL_BG, -1)
        fi.draw_rect(x1, y1, x1 + max(1, int(round((x2 - x1) * ratio))), y2, _COOL_FG, -1)
