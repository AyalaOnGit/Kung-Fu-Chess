# game/

The only subpackage that imports `kungfu_chess` (`ChessEngine`) — every other subpackage
reaches the engine, if at all, through this one's translations. Owns one active `Room` per
in-progress match and the authorization/broadcast/persistence glue around it.

## Files

- **`engine_path.py`** — inserts `ChessEngine/` onto `sys.path` so `import kungfu_chess`
  resolves; every other file here imports this first (idempotent, so doing it per-module is
  cheap and each module is correct standalone regardless of import order).
- **`engine_factory.py`** — `build_game_stack(board=None, cooldown_ms=...)`: thin wrapper
  around `kungfu_chess.engine_builder.build_engine`, defaulting to the standard starting
  position.
- **`commands.py`** — `handle_move`/`handle_jump`: the authorization gate, independent of
  transport (plain data + a `GameEngine` in, `HandleResult` out). Order: role gate (must be
  paired into a match; viewers rejected) → parse the wire payload into `Position`s
  (malformed → `MALFORMED_COMMAND`) → **ownership check against the live board** (the actual
  anti-cheat gate — neither `kungfu_chess.rules.RuleEngine` nor `MoveCommand`/`JumpCommand`
  check who a piece belongs to) → optional piece-kind integrity check → `engine.execute(...)`,
  publishing to the `Bus` on acceptance.
- **`events.py`** — `MoveAccepted`/`JumpAccepted`/`PieceArrived`/`PieceCaptured`/`Promotion`/
  `GameOver` dataclasses published onto the `Bus`. Mirrors `UI/state/game_events.py`'s shape
  (same underlying problem — `GameEngine` emits nothing itself — solved independently on
  each side, since `MultiplayerServer/` and `UI/` are separate top-level packages by design).
- **`engine_bridge.py`** — `EngineEventRelay`: since `GameEngine` has no pub-sub, this diffs a
  `FrozenSnapshot` of the board before/after each tick (`kungfu_chess.observation`) and
  publishes whatever `diff_snapshots` infers as `game/events.py` dataclasses.
- **`rooms.py`** — `Room` (one `GameEngine` + its tick task, addressable by `room_id`) and
  `RoomManager` (the only strong-referencing owner of a `Room`; sessions hold a `room_id`,
  not a `Room` reference). `RoomManager.create_room` wires a room-scoped broadcaster via
  `network.broadcast.Broadcaster` (injected, defaulting to `WebsocketBroadcaster`) and an
  optional event logger; `end_room` runs the full teardown (unsubscribe both, stop the tick
  task, drop the `Room`) in one place.
- **`room_membership.py`** — `RoomMembership`: `(white_user_id, black_user_id)` per active
  `room_id`. Both `main.py`'s `on_paired`/`on_game_over` and `network/dispatch.py`'s
  `create_room`/`join_room` handlers need to read and write the same seats — `on_game_over`
  can't re-derive them from `SessionManager` at game-over time, since a disconnect-timeout
  loser has already been removed from it by then.
- **`rating_service.py`** — `record_match_result(...)`: the one place a finished match's
  outcome becomes an ELO update (`rating/elo.py`) and a persisted row (`db/`).
- **`wire.py`** — translates `game/events.py` dataclasses (which carry `kungfu_chess` model
  objects) into JSON-safe dicts. `network/` must never import `kungfu_chess` directly; this
  module is the seam that lets `network/dispatch.py` broadcast game events without ever
  touching a `Piece`, `Position`, `Color`, or `Kind` object.

## Data flow

`main.py` calls `game.engine_factory.build_game_stack()` (via `RoomManager.create_room`) to
get a `GameEngine`, ticks it every `TICK_INTERVAL_MS` via `Room._run_tick_loop`, and
`EngineEventRelay` diffs+publishes what changed onto that room's `Bus` topic — which
`RoomManager`'s broadcaster fans out to every session in the room (`game/wire.py` doing the
JSON translation) and `game/rating_service.py` consumes on `GameOver` to update ratings.
Meanwhile `commands.py` is the entry point for every incoming move/jump, called from
`network/dispatch.py`.

## Depends on

`kungfu_chess` (`ChessEngine`), `core/` (`Bus`, `protocol`), `network/session.ClientSession`
and `network/broadcast.Broadcaster` (not `network.server`'s concrete `SessionManager`
internals), `db/` + `rating/` (via `rating_service.py`), `observability/` (event logging).
