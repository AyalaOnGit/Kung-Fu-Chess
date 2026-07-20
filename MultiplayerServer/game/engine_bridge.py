"""
Bridges the synchronous, non-event-emitting kungfu_chess GameEngine onto
the async Bus.

kungfu_chess.engine.game_engine.GameEngine has no pub-sub of its own — the
only notifications it offers are the two constructor-injected callables
RealTimeArbiter already uses internally for its own bookkeeping (game_over,
promotion). So, like UI/state/game_facade.py already does for the pygame
client, EngineEventRelay diffs a FrozenSnapshot of the board before/after
each tick and infers events from the difference, instead of subscribing to
anything — there's nothing on the engine side to subscribe to.
"""
from __future__ import annotations
import game.engine_path  # noqa: F401  (must run before any kungfu_chess import)

from typing import List, Optional
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.observation.snapshot_diff import FrozenSnapshot, diff_snapshots

from core.bus import AsyncMessageBus
from game.events import GameEvent, GameOver, PieceArrived, PieceCaptured, Promotion


class EngineEventRelay:
    """
    Call tick() once per server tick, right after engine.wait(ms). Publishes
    every inferred event onto `topic` on the given Bus, in the order
    diff_snapshots produced them.
    """

    def __init__(self, engine: GameEngine, bus: AsyncMessageBus, topic: str):
        self._engine = engine
        self._bus = bus
        self._topic = topic
        self._last_snapshot: Optional[FrozenSnapshot] = FrozenSnapshot.from_board(
            engine.board, engine.game_over,
        )

    def tick(self) -> List[GameEvent]:
        """
        Diff the current board against the last observed snapshot, publish
        every inferred event, and return that same list — so a caller (e.g.
        MatchSession's tick loop, watching for GameOver) can react to what
        just happened without a second subscription to the same topic.
        """
        current = FrozenSnapshot.from_board(self._engine.board, self._engine.game_over)
        events = [_translate(event_type, event_data)
                  for event_type, event_data in diff_snapshots(self._last_snapshot, current, {})]
        for event in events:
            self._bus.publish(self._topic, event)
        self._last_snapshot = current
        return events


def _translate(event_type: str, event_data) -> GameEvent:
    if event_type == 'piece_arrived':
        piece, pos = event_data
        return PieceArrived(piece=piece, pos=pos)
    if event_type == 'piece_captured':
        piece, capturer, pos = event_data
        return PieceCaptured(piece=piece, capturer=capturer, pos=pos)
    if event_type == 'promotion':
        piece, old_kind, new_kind = event_data
        return Promotion(piece=piece, old_kind=old_kind, new_kind=new_kind)
    if event_type == 'game_over':
        winner, loser = event_data
        return GameOver(winner=winner, loser=loser)
    raise ValueError(f'unknown diff event type: {event_type!r}')
