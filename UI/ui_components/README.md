# ui_components/

HUD data subscribers: each one listens to `state.game_events.GameEvent`s from whichever
facade is running (`GameFacade` or `NetworkGameFacade`) and computes something for
`graphics/hud_renderer.py` to draw. None of these render anything themselves — they own
state and expose getters; `graphics/` is what turns that into pixels.

## Files

- **`moves_log_panel.py`** — `MovesLogPanel`: on `MoveAccepted`, converts the move's
  `src_pos`/`dst_pos` to algebraic notation (`col 0 -> 'a'`, `row 7 (white's home rank) ->
  '1'`) and appends it to the moving piece's color's log. `get_moves() -> {'white': [...],
  'black': [...]}`.
- **`score_panel.py`** — `ScorePanel`: on `PieceCaptured`, credits the capturing color (or,
  if `event.capturer is None` — e.g. an airborne-jump capture where the arriving piece is the
  one removed — the captured piece's *opponent* color) with that piece's material value
  (`PIECE_VALUES`) and appends its `Kind` to that color's captured list. `get_score(color)` /
  `get_captured(color)` (the latter returns a copy).
- **`game_over_banner.py`** — `GameOverBanner`: composes a `state.game_events.GameOverInfo`
  from `GameOver` (sets the title) and `RatingUpdate` (fills in ELO deltas) — the two events
  have no ordering guarantee relative to each other (see
  `MultiplayerServer/main.py`'s `on_game_over` docstring), so `get_info()` just reflects
  whatever has arrived so far and returns `None` until at least `GameOver` has landed.
- **`halt_flash.py`** — `HaltFlashTracker`: on `PieceHalted` (a mid-flight piece redirected
  because its destination became occupied), starts a fixed-duration flash for that piece;
  `tick(dt_ms)` expires it. `is_flashing()` / `get_flashing_piece_id()`.
- **`network_status_panel.py`** — `NetworkStatusPanel`: networked play only. On
  `OpponentDisconnected`, starts counting down from `grace_seconds`; any other event (a move,
  arrival, capture, or game-over — i.e. the opponent is clearly back, or the game ended)
  clears it. `get_status_message()` returns the countdown text, or `None`.

## Data flow

`UI/main.py` constructs one instance of each and calls `facade.subscribe(panel.on_event)`
for every one; `graphics/hud_renderer.py`'s setters (`update_score`, `set_moves`,
`set_game_over`, `set_network_status`) are fed from these panels' getters once per frame.

## Depends on

`state.game_events` only (plus `kungfu_chess.model.piece.Color`/`Kind` for
`score_panel.py`/`moves_log_panel.py`'s notation math). Never imports `graphics/` — the
dependency runs one way, `graphics -> state`/`ui_components` data, never back.
