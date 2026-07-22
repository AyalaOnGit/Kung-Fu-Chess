# matchmaking/

ELO-range-based pairing for players who want a random opponent, as an alternative to
`game/rooms.py`'s manual create-room/join-room-by-id flow.

## Files

- **`queue.py`** — `MatchmakingQueue`: plain data structure, pure methods, no `asyncio`
  anywhere in the file. `enqueue(user_id, elo)` / `dequeue(user_id)`, `find_pairings(now,
  max_pairs=None)` (pairs waiting entries within `elo_range` of each other, earliest joiners
  first, each user in at most one pair per call), `expire(now)` (removes and returns anyone
  queued past `timeout_seconds`).
- **`matchmaker_loop.py`** — `MatchmakerLoop`: the only async code in this package. Polls
  `queue.py`'s pure methods roughly once a second, calling `on_paired(white_id, black_id)`
  for every pairing `find_pairings` forms and `on_timeout(user_id)` for every expiry. Pairs
  *everyone it can* each poll — no cap — since `game/rooms.py`'s `Room` supports many
  concurrent matches (an earlier, single-match-slot version of this codebase capped pairing
  at one per poll; that constraint no longer applies). Same `start()`/`stop()` teardown
  discipline as `game/rooms.py`'s `Room`.

## Data flow

`main.py` constructs one `MatchmakingQueue` + `MatchmakerLoop` and wires
`on_paired`/`on_queue_timeout` closures that create a `Room` (via `game/rooms.py`) and notify
both sessions. `network/dispatch.py`'s `queue_join`/`queue_cancel` handlers are the only
other callers, adding/removing a session's own `user_id`.

## Depends on

`core/clock.Clock` only. No `network/`, `game/`, or `kungfu_chess` import — pairing logic
knows nothing about sessions, rooms, or the engine; `main.py`'s callbacks are where those
get connected.
