# animation/

Pure timing/interpolation logic for piece animation — no rendering, no `cv2`. `graphics/`
consumes this to decide *what to draw where*; drawing itself happens there, not here.

## Files

- **`animation_clock.py`** — `AnimationClock`: measures wall-clock delta-time between
  frames via `time.perf_counter` (or an injected `time_source`, for tests).
  `tick() -> dt_ms` returns milliseconds elapsed since the last call.
- **`motion_predictor.py`** — pure functions/types for predicting a piece's pixel position
  mid-flight:
  - `PixelMotion(src_px, dst_px, duration_ms)` — a `NamedTuple` describing one motion.
  - `cell_distance(src, dst)` / `duration_for_distance_ms(cells)` /
    `duration_for_move_ms(src, dst)` — Chebyshev distance and the matching travel time, using
    the same `kungfu_chess.config` constants (`CELL_SIZE_PX`, `PIECE_SPEED_PPS`) the engine
    itself uses, so client-side prediction matches server/engine timing exactly.
  - `interpolate_pixel(motion, elapsed_ms) -> (x, y)` — linear lerp between `src_px`/`dst_px`,
    clamped to the motion's end.
  - `is_motion_complete(motion, elapsed_ms) -> bool`.
- **`piece_animator.py`** — `PieceAnimator(piece, sprite_loader)`: per-piece animation state
  machine (`PieceAnimatorState`: IDLE/MOVING/JUMPING/SHORT_REST/LONG_REST). `set_state(state)`
  loads that state's sprite frames via `graphics.sprite_loader.SpriteLoader` (falling back to
  IDLE, then a blank frame, if a state's sprites aren't found). `tick(dt_ms)` advances the
  current frame and returns the next state's name once a non-looping animation finishes
  (reading `next_state_when_finished` off the loaded `SpriteConfig`). `get_current_frame()`
  returns the `SpriteFrame` to draw.

## Data flow

`graphics/renderer.py`'s `BoardRenderer` owns one `PieceAnimator` per piece (keyed by
`piece.id`), driving its state from the piece's own `PieceState` and ticking it once per
frame. Both `state/game_facade.py` and `network/network_game_facade.py` use
`motion_predictor`'s pure functions directly (via `state/motion_tracking.py`) to compute
`get_pending_motion()`'s `(PixelMotion, elapsed_ms)` — the renderer never predicts motion
itself, it only interpolates what those facades hand it.

## Depends on

`kungfu_chess.config`, `kungfu_chess.model.position.Position`, `graphics.sprite_loader`
(for `piece_animator.py` only). No `cv2`, no `vendor.img` import anywhere in this package.
