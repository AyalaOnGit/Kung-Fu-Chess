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
import pathlib
from logging.handlers import RotatingFileHandler
from typing import Any, Awaitable, Callable, Dict, Iterable

from game.events import GameEvent
from game.wire import to_wire

_LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s: %(message)s'
_DEFAULT_REDACTED_FIELDS = ('password',)
_DEFAULT_LOG_DIR = 'logs'
_DEFAULT_LOG_FILE = 'server.log'
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3

events_logger = logging.getLogger('kungfu_chess.events')
commands_logger = logging.getLogger('kungfu_chess.commands')


def configure_logging(level: int = logging.INFO, log_dir: str = _DEFAULT_LOG_DIR,
                       log_file: str = _DEFAULT_LOG_FILE) -> None:
    """
    Console logging (as before) plus a rotating file handler so server
    activity survives after the console/terminal is gone — logs/ is
    relative to the process's working directory, same convention as
    config.py's DB_PATH.
    """
    logging.basicConfig(level=level, format=_LOG_FORMAT)
    # basicConfig() no-ops if the root logger already has a handler (e.g. under
    # pytest's own log capturing) — set the level explicitly so file logging
    # isn't silently filtered out by a leftover WARNING default.
    logging.getLogger().setLevel(level)

    log_path = pathlib.Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_path / log_file, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding='utf-8',
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    logging.getLogger().addHandler(file_handler)


def redact(data: Dict[str, Any], fields: Iterable[str] = _DEFAULT_REDACTED_FIELDS) -> Dict[str, Any]:
    """Return a copy of data with any of fields replaced by a placeholder."""
    redacted_fields = set(fields)
    return {key: ('<redacted>' if key in redacted_fields else value) for key, value in data.items()}


def log_command(direction: str, session_id: str, envelope_type: str, data: Dict[str, Any]) -> None:
    """
    Log one raw command in either direction ('recv' from a client,
    'sent' back to it), tagged by session_id. Covers what
    make_room_event_logger doesn't: register/login/queue/room commands,
    not just in-room game events — so credentials must be redacted here.
    """
    commands_logger.info('session=%s direction=%s type=%s data=%s', session_id, direction, envelope_type, redact(data))


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
