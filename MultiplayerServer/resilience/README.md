# resilience/

Disconnect/reconnect grace-period tracking: if a player's connection drops mid-game, they
get a grace window to reconnect before being auto-resigned.

## Files

- **`reconnect_state.py`** — `ReconnectState`: pure, `Clock`-injected tracking, no `asyncio`
  anywhere in the file. `mark_disconnected(user_id, role, room_id)` records the drop time;
  `reclaim(user_id)` pops and returns `(role, room_id)` for a reconnecting user, or `None` if
  there's no pending entry; `expire(now)` removes and returns everyone past their grace
  period (`(user_id, role, room_id)` tuples). `role` here is `core.protocol.Role` — imported
  from `core/`, not `network/session.py`, precisely so this file stays transport-agnostic
  (no dependency on `network/`'s package at all).
- **`reconnect_loop.py`** — `ReconnectLoop`: the only async code in this package. Polls
  `ReconnectState.expire()` roughly once a second and calls `on_expired(user_id, role,
  room_id)` for anyone whose grace period ran out without reconnecting. Same `start()`/
  `stop()` teardown discipline as `game/rooms.py`'s `Room` and
  `matchmaking/matchmaker_loop.py`'s `MatchmakerLoop`.

## Data flow

`main.py` wires `on_disconnect` (called from `network/server.py`'s connection handler) to
`ReconnectState.mark_disconnected`, and `ReconnectLoop`'s `on_expired` to
`game/rooms.py`'s `Room.resign(role, 'disconnect_timeout')`. A successful `login` for a
`user_id` still held by `ReconnectState` (via `reclaim`) restores their `role`/`room_id`
instead of treating them as a fresh connection.

## Depends on

`core/` (`Clock`, `Role`) only. No `network/`, `game/`, or `kungfu_chess` import.
