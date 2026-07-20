"""
stdlib logging only — no external logging framework.

§1's "observability/logging_conf.py — LoggingSubscriber registered on
every Bus topic" is implemented per-room rather than via wildcard topic
matching: core/bus.py deliberately only supports exact-topic subscriptions
(a decision made back in Phase 1, revisited and kept here rather than
adding wildcard support just for this), and rooms are created/destroyed
dynamically. game/rooms.py's RoomManager subscribes make_room_event_logger's
handler to each room's own topic exactly as it does for the broadcaster —
added in create_room, removed in end_room. There is no 'global' or
'user:*' topic anywhere in the actual system (nothing ever publishes to
one), so there is nothing to subscribe a logger to there.
"""
from __future__ import annotations
import logging
from typing import Any, Awaitable, Callable, Dict, Iterable

from game.events import GameEvent
from game.wire import to_wire

_LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s: %(message)s'
_DEFAULT_REDACTED_FIELDS = ('password',)

events_logger = logging.getLogger('kungfu_chess.events')
commands_logger = logging.getLogger('kungfu_chess.commands')


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format=_LOG_FORMAT)


def redact(data: Dict[str, Any], fields: Iterable[str] = _DEFAULT_REDACTED_FIELDS) -> Dict[str, Any]:
    """Return a copy of data with any of fields replaced by a placeholder."""
    redacted_fields = set(fields)
    return {key: ('<redacted>' if key in redacted_fields else value) for key, value in data.items()}


def make_room_event_logger(room_id: str) -> Callable[[GameEvent], Awaitable[None]]:
    """
    Build a Bus handler that logs every event published for one room,
    tagged with room_id — the per-room analogue of a LoggingSubscriber on
    a 'room:*' wildcard topic. Game events never carry credentials, so no
    redact() call is needed here — that's for command-level logging
    (register/login payloads), not board-state events.
    """

    async def handler(event: GameEvent) -> None:
        envelope_type, data = to_wire(event)
        events_logger.info('room_id=%s event=%s data=%s', room_id, envelope_type, data)

    return handler
