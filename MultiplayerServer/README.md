# MultiplayerServer

An asyncio websocket server that turns `ChessEngine`'s local, single-process game engine
into a networked multiplayer service: accounts, matchmaking, many concurrent rooms,
disconnect/reconnect handling, and ELO ratings.

## Architecture at a glance

`main.py`'s `run()` is the **composition root** — the only place in this codebase that
constructs a `Database`, `SessionManager`, `AsyncMessageBus`, `RoomManager`,
`MatchmakerLoop`, or `ReconnectLoop`, and the only place that calls `websockets.serve()`.
Every other module receives its collaborators via constructor injection; nothing below
`main.py` reaches for a global or builds another subpackage's top-level object itself.

```
                         ┌─────────────┐
 client ── websocket ──► │ network/    │  transport + command dispatch
                         └──────┬──────┘
                                │ Envelope-decoded commands
                    ┌───────────┼────────────┬─────────────┐
                    ▼           ▼            ▼             ▼
               ┌────────┐  ┌─────────┐  ┌──────────┐  ┌───────────┐
               │ auth/  │  │ game/   │  │matchmaking│  │resilience/│
               │ login/ │  │ Room +  │  │  /queue   │  │ disconnect│
               │register│  │ commands│  │           │  │  grace    │
               └───┬────┘  └────┬────┘  └─────┬─────┘  └─────┬─────┘
                   │            │ imports      │              │
                   ▼            ▼ kungfu_chess  │              │
               ┌────────┐  ┌─────────┐         │              │
               │  db/   │  │ rating/ │◄────────┴──────────────┘
               │sqlite  │  │  elo    │   (main.py's on_game_over wires
               └────────┘  └─────────┘    game/rooms.py's outcome into
                                            rating/elo + db/, via
                                            game/rating_service.py)
```

`core/` and `observability/` are shared-kernel/cross-cutting: every subpackage above can
depend on them, but they depend on nothing else here.

**Domain boundary:** only `game/` imports `kungfu_chess` (`ChessEngine`'s package) — see
`game/engine_path.py`'s docstring. `network/`, `matchmaking/`, `db/`, `auth/` never import it;
`game/wire.py` is the sole translation seam between engine state/events and the JSON wire
format.

## Subpackages

| Subpackage | README |
|---|---|
| `auth/` | [auth/README.md](auth/README.md) |
| `core/` | [core/README.md](core/README.md) |
| `db/` | [db/README.md](db/README.md) |
| `game/` | [game/README.md](game/README.md) |
| `matchmaking/` | [matchmaking/README.md](matchmaking/README.md) |
| `network/` | [network/README.md](network/README.md) |
| `observability/` | [observability/README.md](observability/README.md) |
| `rating/` | [rating/README.md](rating/README.md) |
| `resilience/` | [resilience/README.md](resilience/README.md) |

## Running it

```bash
pip install websockets pytest pytest-asyncio
python main.py            # listens on 0.0.0.0:8765
```

`dev_client.py` is a standalone reference CLI client for manually poking at a running
server (register/login/queue/create-room by hand) — not imported by anything else, and not
a substitute for the real UI client in `UI/play_online.py`.

## Testing

```bash
python -m pytest tests -q     # ~213 tests, mirrors the src layout 1:1 (tests/<pkg>/test_<module>.py)
```

`pytest.ini` sets `asyncio_mode = strict`, matching every async test's explicit
`@pytest.mark.asyncio` marker. `tests/test_main_integration.py` is the one test file that
doesn't mirror a single subpackage — it drives `main.py`'s `run()` itself end to end over a
real (loopback) websocket connection.
