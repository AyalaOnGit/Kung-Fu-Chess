# user_input/

Mouse input handling: turns raw window mouse events into click/jump requests against a
facade. No board/rules knowledge — purely a timing/position state machine.

## Files

- **`mouse_controller.py`** — `MouseController(click_handler, jump_handler=None)`. State
  machine (see the module docstring for the full diagram):
  - A native OS double-click (`MouseEventType.LEFT_DBLCLK`) always triggers `jump_handler`
    directly, resetting state.
  - A `LEFT_DOWN` within `DOUBLE_CLICK_MS` of, and within `DOUBLE_CLICK_RADIUS_PX` of, the
    previous one is read as a manual double-click → `jump_handler`, not `click_handler`.
  - Any other `LEFT_DOWN` is forwarded to `click_handler(x, y)`. If it reports a completed
    destination click (a src→dst move attempt, `click_handler`'s return value is `True`),
    the double-click timer resets fully — a fast click right after on the same cell must
    read as a fresh selection, not a continuation of the just-finished move. Otherwise
    (a selection click) the click's time/position is recorded for the next event's
    double-click check.
  - All other event types (`MOVE`, scroll, etc.) are ignored.

## Data flow

`UI/main.py` constructs one `MouseController` per session, wired to
`facade.request_click`/`facade.request_jump` (`GameFacade` or `NetworkGameFacade` — either
works, since both expose the same two methods), and registers
`mouse_controller.on_mouse_event` as the window's mouse callback
(`graphics.window.Window.set_mouse_callback`).

## Depends on

`vendor.img.MouseEventType`, `ui_config` (`DOUBLE_CLICK_MS`, `DOUBLE_CLICK_RADIUS_PX`).
