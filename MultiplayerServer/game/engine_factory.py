from __future__ import annotations
import game.engine_path  # noqa: F401  (must run before any kungfu_chess import)

from typing import Optional
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.io.board_factory import standard_board
from kungfu_chess.model.board import Board
from kungfu_chess.engine_builder import build_engine
from kungfu_chess.config import COOLDOWN_MS


def build_game_stack(board: Optional[Board] = None, cooldown_ms: int = COOLDOWN_MS) -> GameEngine:
    """
    Build a ready GameEngine for a fresh match.

    Thin wrapper around the real kungfu_chess.engine_builder.build_engine — no new
    bootstrap chain is invented here.

    :param board: starting board; defaults to the standard chess starting
        position (kungfu_chess.io.board_factory.standard_board()).
    :param cooldown_ms: passed straight through to kungfu_chess.engine_builder.build_engine.
    """
    if board is None:
        board = standard_board()
    return build_engine(board, cooldown_ms=cooldown_ms)
