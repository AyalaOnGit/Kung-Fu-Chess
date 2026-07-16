from __future__ import annotations
from collections import defaultdict
from kungfu_chess.model.piece import Color, Kind
from state.game_events import PieceCaptured, GameEvent


class ScorePanel:
    """
    Subscribes to PieceCaptured events and tracks material score + captured piece list.
    """

    PIECE_VALUES = {
        Kind.PAWN: 1, Kind.KNIGHT: 3, Kind.BISHOP: 3,
        Kind.ROOK: 5, Kind.QUEEN: 9, Kind.KING: 999,
    }

    def __init__(self):
        self._score: defaultdict[Color, int] = defaultdict(int)
        # pieces captured BY each color (i.e. enemy pieces they took)
        self._captured: defaultdict[Color, list[Kind]] = defaultdict(list)

    def on_event(self, event: GameEvent) -> None:
        if isinstance(event, PieceCaptured):
            value = self.PIECE_VALUES.get(event.piece.kind, 0)
            winner = event.capturer.color if event.capturer is not None \
                     else event.piece.color.opponent()
            self._score[winner] += value
            self._captured[winner].append(event.piece.kind)

    def get_score(self, color: Color) -> int:
        return self._score[color]

    def get_captured(self, color: Color) -> list[Kind]:
        """Return list of piece Kinds captured BY color (enemy pieces they took)."""
        return list(self._captured[color])
