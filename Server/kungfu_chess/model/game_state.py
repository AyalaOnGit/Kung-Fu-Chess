from kungfu_chess.model.board import Board


class GameState:
    """
    Top-level model container.

    Holds the Board and the game_over flag.
    Does not contain movement rules, timing, or rendering logic.
    """

    def __init__(self, board: Board):
        self.board:     Board = board
        self.game_over: bool  = False
