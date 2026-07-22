# network/

Transport and command routing. Everything a raw websocket connection needs, plus dispatch
of decoded commands to the subpackage that actually handles each one — but never
`kungfu_chess` itself (see `game/README.md`'s boundary note).

## Files

- **`session.py`** — `ClientSession`: one connected client (`session_id`, `websocket`, and
  `role`/`room_id`/`user_id`/`username`, all starting `None`). `role`/`room_id` are only ever
  set together, by server logic (`matchmaking/matchmaker_loop.py`'s pairing or
  `dispatch.py`'s create/join-room handlers) — never directly from a client message.
- **`server.py`** — `SessionManager` (tracks every connected client: `admit`, `remove`,
  `get_by_user_id`, `sessions`) and `build_handler(session_manager, on_admit=, on_message=,
  on_disconnect=)`, which builds the per-connection coroutine `websockets.serve` runs. Stays
  transport-only: the three hooks are injected by `main.py` (via `dispatch.py`), so this
  module never has to import anything game-related to route a message.
- **`dispatch.py`** — Command Pattern: `envelope['type'] -> registered async handler` in a
  `_HANDLERS` dict (`ping`, `move`, `jump`, `check_username`, `register`, `login`,
  `queue_join`, `queue_cancel`, `create_room`, `join_room`). `build_dispatcher(...)` bundles
  every collaborator (`RoomManager`, `SessionManager`, `UsersRepository`,
  `MatchmakingQueue`, `ReconnectState`, `RoomMembership`) into one `DispatchContext` so
  handlers take a uniform `(session, ctx, data)` shape, and returns the `on_message` callback
  `server.py` calls for every raw message. Always returns something to send back to the
  sender — malformed envelopes and unrecognized types get their own error response rather
  than being silently dropped.
- **`broadcast.py`** — `Broadcaster` protocol (`broadcast(sessions, raw) -> None`) +
  `WebsocketBroadcaster`, the concrete implementation. `game/rooms.py`'s `RoomManager`
  depends on this instead of importing `SessionManager`'s concrete type and calling
  `session.websocket.send(...)` directly — the one place game logic needed a way to deliver
  a message without reaching into a transport object itself.

## Data flow

`main.py` builds one `SessionManager`, then `build_dispatcher(...)` (closing over every
subsystem it needs), then `build_handler(session_manager, on_message=<that dispatcher>,
on_disconnect=...)`, and finally passes the result to `websockets.serve`. Every inbound
message: raw text → `server.py` → `dispatch.py` decodes the `Envelope` → routes by `type` to
one `_HANDLERS` entry → that handler calls into `auth/`, `game/`, `matchmaking/`, or
`resilience/` as needed → returns an `Envelope` encoded back to `server.py` to send to the
sender. Broadcasts to *other* sessions in the same room happen separately, via
`game/rooms.py`'s `Broadcaster` — `dispatch.py`'s return value is always the direct reply to
the sender alone.

## Depends on

`core/` (`Bus`, `protocol`), `auth/`, `game/` (`RoomManager`, `RoomMembership`, command
handlers), `matchmaking/`, `resilience/`, `db/` (`UsersRepository`, via `dispatch.py`). Never
imports `kungfu_chess` directly.
