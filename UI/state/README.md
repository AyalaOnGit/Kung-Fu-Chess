# state/

The observer/event system and both `GameFacade` implementations — the seam between
"whatever is actually running the game" (a local `ChessEngine` `GameEngine`, or a
server-authoritative mirror board) and every UI component that reacts to it.

## Files

- **`observer.py`** — `Subject[EventType]`: minimal pub/sub. `subscribe(callback)` /
  `publish(event)`; a subscriber that raises is caught and logged (`print`), not allowed to
  break the other subscribers or the publisher.
- **`game_events.py`** — every event dataclass a facade can publish (`MoveAccepted`,
  `MoveRejected`, `PieceArrived`, `PieceCaptured`, `PieceHalted`, `Promotion`, `GameOver`,
  `OpponentDisconnected`, `RatingUpdate`) plus `GameOverInfo` (not itself a published event —
  `ui_components/game_over_banner.py` composes one from `GameOver` + `RatingUpdate` for
  `graphics/hud_renderer.py` to draw). `GameOverInfo` lives here rather than in
  `game_over_banner.py` specifically so `graphics/` depends on `state/` for it, not on
  `ui_components/`.
- **`motion_tracking.py`** — `PendingMotionData` (the dataclass both facades track in-flight
  pieces with) and `pixel_motion_for(motion_data, mapper, now_ms)` (the pixel-position/
  elapsed-time computation `get_pending_motion` needs) — shared so `game_facade.py` and
  `network/network_game_facade.py` don't each keep their own copy in sync by convention.
- **`game_facade.py`** — `GameFacade(engine, mapper)`: the local-play facade. Routes clicks/
  jumps to a `kungfu_chess.interaction.Controller`, tracks pending motions
  (`PendingMotionData`), and — since `GameEngine` itself emits no events — diffs
  `kungfu_chess.observation.FrozenSnapshot`s before/after each completed motion to infer and
  publish events. **Note**: the very first motion to complete in a fresh `GameFacade`'s
  lifetime only establishes that diff's initial baseline snapshot and publishes nothing (see
  `_diff_and_publish_events`) — every motion after the first is diffed normally. This doesn't
  manifest in practice since `main.py`'s render loop calls `tick()` continuously well before
  any click can complete a motion, but it's worth knowing if you're driving a `GameFacade`
  directly (e.g. in a test) rather than through the real render loop.

## Data flow

`UI/main.py` constructs one `GameFacade` (local) or, lazily, one `NetworkGameFacade`
(networked — see `network/README.md`) and subscribes every `ui_components/` panel plus
`audio.SoundManager` to it. Both facades expose the identical public interface by design, so
`main.py`'s shared `_run_game_loop()` and everything downstream of it never branch on which
one they're holding.

## Depends on

`kungfu_chess` (model, engine, interaction, observation — `game_facade.py` only),
`animation.motion_predictor`. `network/network_game_facade.py` lives in `UI/network/`, not
here, but implements the same interface these files define by convention.
