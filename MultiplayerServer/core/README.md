# core/

Shared-kernel module: three small, unrelated-but-cross-cutting concerns every other
subpackage may need, kept together so nothing else has to reach into a sibling
domain package for them.

## Files

- **`bus.py`** — `AsyncMessageBus`: topic-based async pub/sub. `subscribe(topic, handler)`
  gives each subscriber its own `asyncio.Queue` and a consumer task; `publish(topic, event)`
  only enqueues — it never awaits a handler directly, so one slow/stuck subscriber can't
  block the publisher or other subscribers. Returns an `Unsubscribe` callable. Used by
  `game/rooms.py` to fan out engine events per room.
- **`clock.py`** — `Clock` `Protocol` (`now() -> float`, seconds), with `RealClock` (backed by
  `time.monotonic()`) for production and `FakeClock` (manually `advance()`d) for tests.
  Injected into anything with a notion of elapsed time: `matchmaking/queue.py`,
  `resilience/reconnect_state.py`, `matchmaking/matchmaker_loop.py`,
  `resilience/reconnect_loop.py`.
- **`protocol.py`** — the wire contract: `Envelope` (`type` + `data` dict), `encode`/`decode`
  to/from JSON, `MalformedEnvelopeError`, `ErrorCode` (the closed set of error strings a client
  can receive — several reuse `kungfu_chess.config.REASON_*` strings verbatim so
  `game/commands.py` can map an engine `CommandResult.reason` straight to an `ErrorCode` with
  no translation table), and `Role` (`WHITE`/`BLACK`/`VIEWER`, plus `.can_move`). `Role` lives
  here rather than in `network/session.py` specifically so that `resilience/` — documented as
  transport-agnostic — can depend on it without reaching into `network/`.

## Depends on

Nothing else in this repo. Every other subpackage may depend on `core/`; it never depends
back on any of them.
