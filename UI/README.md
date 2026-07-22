# UI

The game client: local two-player hotseat play, and networked play against
`MultiplayerServer/`. All rendering goes through one class — `vendor/img.py`'s `Img` — the
sole OpenCV boundary in this codebase; nothing else here calls `cv2` directly.

## Entry points

- **`python main.py`** — local hotseat: both colors on one board/window, driven by a local
  `ChessEngine` `GameEngine` (via `state/game_facade.py`'s `GameFacade`).
- **`python play_online.py`** — networked play: `home_shell.py`'s stdin login/registration
  flow, then `lobby_window.py`'s Play/Room lobby, then `main.py`'s game loop again — but this
  time driven by `network/network_game_facade.py`'s `NetworkGameFacade`, which mirrors
  `GameFacade`'s exact public interface so `main.py`'s render loop, `BoardRenderer`,
  `HudRenderer`, and every `ui_components/` panel work against either one unmodified.

## Layout

```
main.py            Game-loop entrypoint; shared by both local and networked play
home_shell.py       Stdin login/registration flow (networked play only)
lobby_window.py     Tkinter Play/Room lobby (networked play only -- see "The one exception" below)
play_online.py      Chains home_shell -> lobby_window -> main.py's networked path
path_bootstrap.py   Puts ChessEngine/ onto sys.path so `import kungfu_chess` resolves
ui_config.py        All UI-only tunables: layout, colors, timings
vendor/img.py       The Img class -- see "The Img boundary" below
assets/             board.png, piece sprite sets, generated sound tones
graphics/           Rendering + window/mouse management        -- graphics/README.md
animation/          Piece animation state machine + motion interpolation -- animation/README.md
network/            Client-side wire protocol + websocket client -- network/README.md
state/              Observer pattern, game events, local + networked GameFacade -- state/README.md
ui_components/      HUD data subscribers (moves log, score, game-over, ...) -- ui_components/README.md
audio/              Generated-tone sound effects -- audio/README.md
user_input/         Mouse click/double-click/jump state machine -- user_input/README.md
tests/              Unit tests, one file per module (conftest.py handles the sys.path bootstrap)
```

## The `Img` boundary

Every pixel this app draws — board, pieces, HUD, selection highlight, cooldown bars, the
game-over dialog — goes through `vendor/img.py`'s `Img` class: `read`/`resize`/`blit`/
`fill_rect_blend`/`draw_rect`/`draw_line`/`put_text`, plus window management
(`create_window`/`show_in_window`/`set_mouse_callback`/`wait_key`/`is_window_visible`/
`destroy_window`) and `MouseEventType`, the one place cv2's mouse-event constants leak out.
No other graphics/UI library (PyGame, SFML, etc.) is used anywhere in this project.

**The one exception**: `lobby_window.py`'s pre-game login/room-selection screen uses
Tkinter, not `Img`. This is a deliberate, scoped exception — the `Img`-only rule applies to
the actual game window (board, pieces, HUD, animation); the lobby is separate chrome the
player never sees at the same time as the board. `lobby_window.py`'s `LobbyController` (the
actual Play/Room decision logic) is Tk-free and fully unit-tested; `_LobbyApp`/`_RoomDialog`
are the thin Tk shell around it.

## Setup

```bash
pip install -r requirements.txt   # pytest, opencv-python, numpy
```
`websockets` is also required for networked play (`play_online.py`, `network/`) —
already a dependency of `MultiplayerServer/`, so if you're running both from the same
environment it's already installed.

## Testing

```bash
python -m pytest tests -q     # ~161 tests
```
Works the same whether run from inside `UI/` or as `pytest UI/tests` from the repo root —
`tests/conftest.py` handles the `sys.path`/`ChessEngine` bootstrap once, centrally.
