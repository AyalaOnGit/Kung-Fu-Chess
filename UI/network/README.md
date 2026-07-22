# network/ (UI)

Everything networked play needs on the client side: the wire format, the websocket
connection itself, and the facade that turns server events into the same UI events local
play produces.

## Files

- **`protocol.py`** — `Envelope`/`ErrorCode`/`encode`/`decode`/`MalformedEnvelopeError`, a
  **deliberate duplicate** of `MultiplayerServer/core/protocol.py`. Not imported from there:
  `MultiplayerServer/`'s subpackages are meant to sit directly on `sys.path` as top-level
  modules (see its own `dev_client.py`), which would collide with `UI/network/`'s and
  `UI/observability/`'s own package names if done from this side too. The wire format is
  tiny and stable, so a client-side copy is cheaper than resolving that collision.
- **`ws_client.py`** — `WsClient(uri)`: since `UI/main.py`'s render loop is fully
  synchronous, `WsClient` runs its own `asyncio` event loop on a dedicated background thread
  and exposes a synchronous, thread-safe interface instead: `connect()` blocks until
  connected (or raises), `send(envelope_type, data)` enqueues a command onto the network
  thread, `poll_events()` non-blockingly drains everything received since the last call. The
  render loop calls `poll_events()` once per frame, exactly like it calls `facade.tick(dt_ms)`.
- **`network_game_facade.py`** — `NetworkGameFacade`: the server-authoritative counterpart to
  `state/game_facade.py`'s `GameFacade`, exposing the identical public interface
  (`subscribe`/`request_click`/`request_jump`/`tick`/`get_selected_pos`/`get_cooldown_ratio`/
  `get_pending_motion`) so nothing downstream (`BoardRenderer`, `HudRenderer`,
  `ui_components/*`) needs to know which one it's holding. Where `GameFacade` owns a live
  `GameEngine` and mutates it directly, `NetworkGameFacade` owns a *mirror*
  `kungfu_chess.model.board.Board` that it only updates in response to wire events the
  server broadcasts — clicks/jumps are sent as commands and applied locally only once the
  server's own broadcast confirms them. Motion/cooldown timing is predicted client-side the
  same way `GameFacade` does (`state/motion_tracking.py`, same `kungfu_chess.config`
  constants), since the server streams accept/arrive/capture events, not per-frame positions.

## Data flow

`play_online.py` builds one `WsClient`, connects it, and hands it to `NetworkGameFacade`.
Every frame, `NetworkGameFacade.tick(dt_ms)` calls `ws_client.poll_events()` and translates
each `Envelope` (`move_accepted`, `piece_arrived`, `piece_captured`, `game_over`,
`rating_update`, `state_sync`, ...) into the same `state/game_events.py` dataclasses
`GameFacade` publishes for local play — so every other UI component is oblivious to which
facade is actually driving the board.

## Depends on

`kungfu_chess.model` (mirror board), `state.game_events`, `state.motion_tracking`,
`state.observer`, `animation.motion_predictor`, `observability.logging_conf`.
