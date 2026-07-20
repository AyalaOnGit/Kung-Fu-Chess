"""
Board renderer: draws the board and all pieces with animations.
"""
from __future__ import annotations
from typing import Optional, Dict, TYPE_CHECKING
import numpy as np

from vendor.img import Img
from graphics.sprite_loader import SpriteLoader
from animation.piece_animator import PieceAnimator, PieceAnimatorState
from animation.motion_predictor import interpolate_pixel
from kungfu_chess.config import CELL_SIZE_PX
from kungfu_chess.model.position import Position
from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece, PieceState
from kungfu_chess.input.board_mapper import BoardMapper
from ui_config import (
    PIECE_SCALE, SELECTION_COLOR, SELECTION_BORDER_COLOR, SELECTION_BORDER_THICKNESS,
    SELECTION_FILL_ALPHA, JUMP_RING_COLOR, JUMP_RING_THICKNESS, JUMP_RING_MARGIN_PX,
    COOLDOWN_BAR_BG_COLOR, COOLDOWN_BAR_FG_COLOR, COOLDOWN_BAR_HEIGHT_PX, COOLDOWN_BAR_MARGIN_PX,
    HALT_FLASH_COLOR, HALT_FLASH_THICKNESS,
)

if TYPE_CHECKING:
    from state.game_facade import GameFacade


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
        self._halted_piece_id: Optional[int] = None

    def set_selection(self, pos: Optional[Position]) -> None:
        self._selected_pos = pos

    def set_halted_piece(self, piece_id: Optional[int]) -> None:
        """Mark a piece as currently flashing (was redirected/halted mid-flight)."""
        self._halted_piece_id = piece_id

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
        frame_img = Img()
        frame_img.img = self._board_img.img.copy()
        frame_img.to_bgra()

        static_pieces: list[tuple] = []
        moving_pieces: list[tuple] = []

        for piece in self._board.all_pieces():
            pos = piece.cell
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
            self._draw_selection(frame_img, self._selected_pos)

        for piece, cx, cy, cw, ch in static_pieces:
            self._draw_piece(frame_img, piece, cx, cy, cw, ch)
        for piece, cx, cy, cw, ch in moving_pieces:
            self._draw_piece(frame_img, piece, cx, cy, cw, ch)

        return frame_img.img

    def _draw_selection(self, frame_img: Img, pos: Position) -> None:
        x, y   = self._mapper.position_to_pixel(pos)
        cw, ch = self._mapper.cell_size(pos)
        frame_img.fill_rect_blend(x + 2, y + 2, x + cw - 2, y + ch - 2,
                                   SELECTION_COLOR, SELECTION_FILL_ALPHA)
        frame_img.draw_rect(x + 2, y + 2, x + cw - 2, y + ch - 2,
                             SELECTION_BORDER_COLOR, SELECTION_BORDER_THICKNESS)

    def _draw_piece(self, frame_img: Img, piece: Piece,
                    cell_x: int, cell_y: int, cell_w: int, cell_h: int) -> None:
        animator   = self._get_animator(piece)
        piece_size = max(1, int(round(min(cell_w, cell_h) * PIECE_SCALE)))
        try:
            sprite_img = Img()
            sprite_img.img = animator.get_current_frame().image
            sprite_img.to_bgra()

            sh, sw = sprite_img.img.shape[:2]
            scale  = min(piece_size / float(sw), piece_size / float(sh))
            new_w  = max(1, int(round(sw * scale)))
            new_h  = max(1, int(round(sh * scale)))
            if new_w != sw or new_h != sh:
                sprite_img.resize(new_w, new_h)
            sh, sw = sprite_img.img.shape[:2]

            px_x = cell_x + (cell_w - sw) // 2
            px_y = cell_y + (cell_h - sh) // 2
            frame_img.blit(sprite_img, px_x, px_y)

            if piece.id == self._halted_piece_id:
                self._draw_halt_flash(frame_img, cell_x, cell_y, cell_w, cell_h)

            if piece.state is PieceState.JUMPING:
                self._draw_jump_ring(frame_img, cell_x, cell_y, cell_w, cell_h)
            elif piece.state is PieceState.COOLING:
                self._draw_cooldown_bar(frame_img, piece, cell_x, cell_y, cell_w, cell_h)

        except Exception as e:
            print(f"Error drawing piece {piece.token()}: {e}")

    def _draw_jump_ring(self, frame_img: Img,
                        cell_x: int, cell_y: int, cell_w: int, cell_h: int) -> None:
        m = JUMP_RING_MARGIN_PX
        frame_img.draw_rect(cell_x + m, cell_y + m,
                             cell_x + cell_w - m, cell_y + cell_h - m,
                             JUMP_RING_COLOR, JUMP_RING_THICKNESS)

    def _draw_halt_flash(self, frame_img: Img,
                         cell_x: int, cell_y: int, cell_w: int, cell_h: int) -> None:
        m = JUMP_RING_MARGIN_PX
        frame_img.draw_rect(cell_x + m, cell_y + m,
                             cell_x + cell_w - m, cell_y + cell_h - m,
                             HALT_FLASH_COLOR, HALT_FLASH_THICKNESS)

    def _draw_cooldown_bar(self, frame_img: Img, piece: Piece,
                           cell_x: int, cell_y: int, cell_w: int, cell_h: int) -> None:
        ratio = self._facade.get_cooldown_ratio(piece)
        if ratio <= 0.0:
            return
        x1 = cell_x + COOLDOWN_BAR_MARGIN_PX
        x2 = cell_x + cell_w - COOLDOWN_BAR_MARGIN_PX
        y2 = cell_y + cell_h - COOLDOWN_BAR_MARGIN_PX
        y1 = y2 - COOLDOWN_BAR_HEIGHT_PX
        frame_img.draw_rect(x1, y1, x2, y2, COOLDOWN_BAR_BG_COLOR, -1)
        frame_img.draw_rect(x1, y1, x1 + max(1, int(round((x2 - x1) * ratio))), y2,
                             COOLDOWN_BAR_FG_COLOR, -1)
