# observability/

Server-side logging. Stdlib `logging` only — no external logging framework.

## Files

- **`logging_conf.py`**:
  - `configure_logging(level=, log_dir='logs', log_file='server.log')` — console logging
    plus a rotating file handler (5MB × 3 backups), so activity survives after the terminal
    is gone. Called once, at startup, by `main.py`.
  - `redact(data, fields=('password',))` — returns a copy of a payload dict with sensitive
    fields replaced by a placeholder.
  - `log_command(direction, session_id, envelope_type, data)` — logs one raw command in
    either direction (`'recv'`/`'sent'`), redacted. Covers everything a room-scoped logger
    doesn't: register/login/queue/room commands, not just in-room game events.
  - `make_room_event_logger(room_id)` — builds a `Bus` handler that logs every game event
    published for one room, tagged with `room_id`. Since `core/bus.py` only supports
    exact-topic subscriptions (no wildcards) and rooms are created/destroyed dynamically,
    `game/rooms.py`'s `RoomManager` subscribes one of these per room in `create_room` and
    unsubscribes it in `end_room` — the same lifecycle as the room's broadcaster. Game
    events never carry credentials, so no `redact()` call is needed here.

## Depends on

`game/events.GameEvent`, `game/wire.to_wire` (to render an event for the log line). Nothing
else in this repo depends on `observability/` for anything but these four functions.
