# Kung-Fu Chess

Real-time chess: no turns, no waiting. Both players can issue commands at
any moment; each move takes real time to travel across the board (further
= slower), and a piece that just arrived needs a short cooldown before it
can move again. A piece mid-flight can be intercepted — including by a
king, which ends the game the instant it's captured. There's also a
**jump**: a piece can leap briefly off its own cell and land back on it,
capturing anything that arrives underneath it while it's airborne.

## Core idea

Classic chess is turn-based and static once a move resolves. This project
replaces that with a real-time, physics-like layer: every move/jump is a
timed event resolved against a simulated clock, not an instantaneous board
update. That's the whole reason the engine (`ChessEngine/`) is split from
both a networked multiplayer server and a local UI — the same timing rules
have to produce identical results whether two people are sitting at one
keyboard or playing over a websocket from different machines.

## Tech stack

- **Python 3.13**, no framework — every subsystem is plain, dependency-injected Python.
- **Rendering**: OpenCV (`cv2`), but never called directly outside one file — `UI/vendor/img.py`'s `Img` class is the sole graphics primitive for every board, piece, HUD element, animation, and dialog in the game window. No PyGame, Tkinter-for-gameplay, or other GUI toolkit is used inside the game window (the separate pre-game login/lobby screen is a documented exception — see [UI/README.md](UI/README.md)).
- **Networking**: `asyncio` + the `websockets` library for the multiplayer server and client.
- **Persistence**: `sqlite3` (accounts, ELO ratings, match history).
- **Testing**: `pytest` (+ `pytest-asyncio` for the async server code).

## Repository structure

Three independent top-level Python packages, each with its own test suite:

```
ChessEngine/        Pure, shared real-time chess engine library (no I/O, no rendering)
MultiplayerServer/  Asyncio websocket server: matchmaking, rooms, accounts, ratings
UI/                 OpenCV/Img-based client: local hotseat play and networked play
```

`MultiplayerServer/` and `UI/` are both **consumers** of `ChessEngine/` — neither depends on
the other, and `ChessEngine/` depends on nothing in this repo. Each subsystem puts
`ChessEngine/` onto `sys.path` itself at import time (`MultiplayerServer/game/engine_path.py`,
`UI/path_bootstrap.py`) rather than the engine being installed as a package, so the three
can be developed and tested independently without a build/install step.

```
┌─────────────────┐        ┌──────────────────┐
│  MultiplayerServer │◄────►│   UI (networked)  │
│  (websocket server) │      │  play_online.py   │
└─────────┬─────────┘        └────────┬─────────┘
          │                            │
          └──────────┬─────────────────┘
                      ▼
              ┌──────────────┐         ┌───────────────┐
              │ ChessEngine/ │◄────────┤ UI (local)     │
              │ kungfu_chess │         │ main.py        │
              └──────────────┘         └───────────────┘
```

See each subsystem's own README for its internal architecture:
[ChessEngine/README.md](ChessEngine/README.md) ·
[MultiplayerServer/README.md](MultiplayerServer/README.md) ·
[UI/README.md](UI/README.md)

## Setup

Requires Python 3.13+ (or any 3.10+ interpreter — nothing version-specific is used).

```bash
# Engine: pure stdlib, only pytest needed to run its tests
pip install pytest

# Multiplayer server
pip install websockets pytest pytest-asyncio

# UI client
pip install -r UI/requirements.txt   # pytest, opencv-python, numpy
```

There's no repo-wide virtualenv/requirements file by design — the three subsystems are
meant to be independently runnable, so they're installed independently too.

## Running it

**Local, one-keyboard game** (both colors on one board/window):
```bash
cd UI
python main.py
```

**Networked play** — start the server, then run the client twice (two players):
```bash
cd MultiplayerServer
python main.py                # listens on 0.0.0.0:8765

# in another terminal, once per player:
cd UI
python play_online.py         # prompts for login/registration, then a Play/Room lobby
```

**Engine only** (no UI, no server) — useful for scripting/exploring the rules in isolation:
```python
from kungfu_chess.io.board_parser import parse_board
from kungfu_chess.engine_builder import build_script_runner

board = parse_board(["wR . . .", ". . . ."])
_, runner = build_script_runner(board)
print(runner.run(["click 50 50", "click 350 50", "wait 3000", "print board"]))
```
(run with `ChessEngine/` on `sys.path`, or from inside `ChessEngine/` itself)

## Testing

Each subsystem has its own suite and `pytest.ini` — run them from inside each directory,
or point pytest at the subdirectory from the repo root:

```bash
cd ChessEngine        && python -m pytest tests -q   #  ~103 tests
cd MultiplayerServer   && python -m pytest tests -q   #  ~213 tests
cd UI                  && python -m pytest tests -q   #  ~161 tests
```

All three are independent — there is no repo-wide test runner, matching the
independent-subsystem design above.
