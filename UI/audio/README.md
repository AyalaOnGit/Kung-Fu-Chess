# audio/

Sound effects, synthesized at runtime rather than shipped as audio assets.

## Files

- **`tone_generator.py`** — `generate_tone(path, frequencies_hz, duration_ms)`: writes a
  mono 16-bit PCM WAV file at `path` — the sum of `frequencies_hz` (a short chord reads as a
  more distinct "blip" than one sine tone), linearly faded in/out over 10ms to avoid an
  audible click at the edges. Stdlib `wave`/`array`/`math` only, no external audio assets or
  dependencies. `ensure_tone(path, frequencies_hz, duration_ms)` generates only if `path`
  doesn't already exist, returning it either way — so the six tone files
  (`assets/sounds/*.wav`) are generated once, on first run, and reused after.
- **`sound_manager.py`** — `SoundManager(my_color=None, enabled=True)`: subscribes to the
  same `state.game_events` `Subject` every other UI component uses, and plays a tone for
  each relevant event via stdlib `winsound` (Windows-only, matching this project's
  environment — silently no-ops on any other platform rather than crashing). `play_start()`
  for the game-start tone; `on_event(event)` plays `move`/`capture` tones, and — for
  `GameOver` — `win`/`lose`/neutral `game_over` depending on whether `my_color` matches the
  winner (`my_color=None`, e.g. local hotseat where both colors are "mine", always plays the
  neutral tone).

## Depends on

`state.game_events` (`GameEvent`, `GameOver`, `MoveAccepted`, `PieceCaptured`),
`kungfu_chess.model.piece.Color`. No third-party audio library — `winsound` is stdlib.
