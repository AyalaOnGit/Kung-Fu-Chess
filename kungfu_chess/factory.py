from __future__ import annotations
from kungfu_chess.model.board import Board
from kungfu_chess.model.game_state import GameState
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.realtime.real_time_arbiter import RealTimeArbiter
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.input.board_mapper import BoardMapper
from kungfu_chess.input.controller import Controller
from kungfu_chess.texttests.script_runner import ScriptRunner


def build_engine(board: Board) -> GameEngine:
    """Wire all layers together and return a ready GameEngine."""
    state   = GameState(board)
    engine  = GameEngine.__new__(GameEngine)
    arbiter = RealTimeArbiter(
        board,
        on_king_captured=engine.on_king_captured,
        on_piece_arrived=engine.on_piece_arrived,
    )
    GameEngine.__init__(engine, state, RuleEngine(), arbiter)
    return engine


def build_script_runner(board: Board) -> tuple:
    """Return a (GameEngine, ScriptRunner) pair ready to run text scripts."""
    engine     = build_engine(board)
    mapper     = BoardMapper(board.width, board.height)
    controller = Controller(engine, mapper)
    runner     = ScriptRunner(engine, controller)
    return engine, runner
