# ChessEngine

The real-time chess rules engine — a pure Python library with no I/O, no rendering, and no
networking. `MultiplayerServer/` and `UI/` both consume it; it consumes nothing from either.

## Why this is its own package

The whole point of "kung-fu chess" is that moves resolve over real time (travel duration,
cooldowns, mid-flight interception), not instantly on click. That timing logic has to
produce byte-for-byte identical results whether it's driving a local hotseat game or a
networked match refereed by `MultiplayerServer/` — so it lives here, once, and both
consumers import it rather than each re-implementing (or subtly diverging on) the rules.

## Layout

```
kungfu_chess/
  model/        Pure data: Board, Piece, Position, GameState — no behavior beyond
                 their own invariants (see kungfu_chess/README.md)
  rules/        Chess legality (per-piece move rules), read-only
  realtime/     Motion/jump/cooldown timing, chess-rule-agnostic
  engine/       Application-service coordinator (GameEngine) + command objects
  interaction/  Pixel <-> board-position translation, click/jump -> command
  io/           Text board (de)serialization -- parsing/printing, standard setup
  observation/  Snapshot diffing -- infers events (arrived/captured/promoted/game_over)
                 from two point-in-time Board copies, since GameEngine itself emits none
  scripting/    Text-script interpreter (click/jump/wait/print board) -- production
                 code, not test scaffolding, despite the name's proximity to tests/
  factory.py -> see engine_builder.py; wires model+rules+realtime+engine into a
                 ready GameEngine (build_engine) or GameEngine+ScriptRunner pair
                 (build_script_runner)
tests/
  unit/         One file per kungfu_chess/ subpackage
  integration/  End-to-end script_runner tests
```

Full architecture, data flow, and the boundary rules between these subpackages are in
[kungfu_chess/README.md](kungfu_chess/README.md) — read that before modifying anything here.

## Using it

```python
from kungfu_chess.io.board_factory import standard_board
from kungfu_chess.engine_builder import build_engine
from kungfu_chess.engine.commands import MoveCommand
from kungfu_chess.model.position import Position

engine = build_engine(standard_board())
engine.execute(MoveCommand(Position(6, 0), Position(4, 0)))  # a2-a4
engine.wait(1000)  # advance the simulated clock by 1000ms
```

There is no standalone CLI entrypoint in this directory — `MultiplayerServer/main.py` and
`UI/main.py`/`UI/play_online.py` are the two real consumers. (An earlier `main.py` here read
board/command scripts from stdin, but it duplicated `kungfu_chess/scripting/script_runner.py`
and its generic name collided with both consumers' own `main.py` under their shared
`sys.path` trick, so it was removed; use `build_script_runner` directly, as above and in
`tests/integration/test_script_runner.py`, for the same functionality.)

## Testing

```bash
python -m pytest tests -q
```

No dependencies beyond `pytest` — the engine itself is pure stdlib Python (only `numpy`-free,
`cv2`-free, `asyncio`-free code lives here).
