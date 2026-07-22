# graphics/

Everything that turns board/game state into pixels, plus the window/mouse plumbing around
it. All actual drawing goes through `vendor/img.py`'s `Img` — see the root `UI/README.md`'s
"The `Img` boundary" section.

## Files

- **`window.py`** — `Window`: non-blocking window controller. `display_frame(frame, fps=)`
  shows one already-composed frame per call, scaled to the current zoom level (`+`/`-` keys,
  handled internally); `set_mouse_callback(callback)` wires a mouse handler, mapping scaled
  pixel coordinates back to logical (unscaled) ones before forwarding, and silently ignores
  any cv2 mouse event this app doesn't act on (scroll, drag, etc. — cv2 delivers all of them
  through the same callback). `is_open()`/`close()` for lifecycle. This is the one file
  outside `vendor/img.py` that deals with `MouseEventType`.
- **`sprite_loader.py`** — `SpriteLoader(pieces_dir)`: loads and caches piece animation
  frames from `<PIECE_CODE>/states/<STATE>/sprites/*.png` + a sibling `config.json`
  (`frames_per_sec`, `is_loop`, `next_state_when_finished`). `load_frames(piece_code, state)`
  raises `FileNotFoundError` if that piece/state isn't on disk (with one fallback: a single
  nested subdirectory, e.g. `assets/pieces1/pieces1/RB/...`, is transparently tried too).
  `get_config(piece_code, state)` populates its cache via `load_frames` if needed.
- **`renderer.py`** — `BoardRenderer(board, sprite_loader, board_img_path, facade, mapper)`:
  composes one frame per call to `render(dt_ms)`. For each piece on the board: gets (or
  creates) its `animation.PieceAnimator`, ticks it, and either interpolates a pixel position
  from `facade.get_pending_motion(piece.id)` (if in flight) or places it statically via
  `mapper.position_to_pixel`. Also draws the selection highlight, jump rings, halt flashes,
  and cooldown bars (`facade.get_cooldown_ratio(piece)`). `facade` is duck-typed —
  `state.GameFacade` or `network.NetworkGameFacade`, whichever `UI/main.py` is holding.
- **`hud_renderer.py`** — `HudRenderer(board_width, board_height, ...)`: composes the sidebar
  (player names/ELO, captured-piece thumbnails + score, moves log) alongside the board frame,
  plus the networked-play header (`set_my_role`/`set_room_id`/`set_network_status`) and the
  end-of-game dialog overlay (`set_game_over(GameOverInfo)`, from `state/game_events.py`).
  `ThumbnailCache` (in the same file) loads and caches small idle-pose piece thumbnails for
  the captured-material display.

## Data flow

`UI/main.py` builds one `Window`, `SpriteLoader`, `BoardRenderer`, and `HudRenderer` per game
session. Every frame: `BoardRenderer.render(dt_ms)` returns a board-sized frame,
`HudRenderer.render(board_frame)` composes the full sidebar+board frame from it, and
`Window.display_frame(...)` shows the result. `ui_components/`'s panels (subscribed to the
same facade events) feed their computed state (score, moves, game-over info) into
`HudRenderer` via its setters — `graphics/` never imports `ui_components/` directly for
anything but the `GameOverInfo` *type*, which now lives in `state/game_events.py` precisely
so this direction (`graphics -> state`, not `graphics -> ui_components`) holds.

## Depends on

`vendor.img`, `animation/`, `kungfu_chess.model`/`kungfu_chess.interaction.BoardMapper`,
`state.game_events.GameOverInfo`, `ui_config`. Never imports `ui_components/` or `network/`.
