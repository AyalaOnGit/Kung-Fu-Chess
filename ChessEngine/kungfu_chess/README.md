# kungfu_chess — architecture

A layered library with a strict, one-directional dependency graph and no cycles:

```
model  <──  rules
  ▲     <──  realtime  (+ config)
  ▲     <──  engine     (+ rules, realtime, config)
  ▲     <──  interaction (+ engine)
  ▲     <──  io
  ▲     <──  observation
                 engine, interaction, io  <──  scripting
```

`model/` is the only subpackage every other one depends on; it depends on nothing. No
subpackage below reaches back up into a caller — verified in code review, not just by
convention: e.g. `rules/` never imports `engine/`, and `realtime/` never imports `rules/`.

## Data flow, end to end

1. **`io.board_parser`/`io.board_factory`** produce a `model.Board` (from text, or the
   standard starting position).
2. **`engine_builder.build_engine(board)`** wires a `model.GameState` (the board + a
   `game_over` flag), a `rules.RuleEngine`, and a `realtime.RealTimeArbiter` into a
   `engine.GameEngine` — the thing every consumer actually holds and calls.
3. A caller (UI click, network command) builds an **`engine.commands.MoveCommand`/
   `JumpCommand`** — usually via **`interaction.Controller`**, which turns raw pixel clicks
   into commands using **`interaction.BoardMapper`** for the pixel↔`Position` translation —
   and passes it to `GameEngine.execute(command)`.
4. The command asks `rules.RuleEngine` whether the move is legal, then hands off to
   `realtime.RealTimeArbiter` to actually start the timed motion/jump.
5. Every tick, the caller calls **`GameEngine.wait(dt_ms)`**, which advances the arbiter's
   simulated clock and resolves any arrivals: capturing at the destination, applying
   cooldowns, calling back into `GameEngine` for anything rule-specific (see below).
6. Since `GameEngine` itself emits no events, consumers who need them (UI, network wire
   format) take two **`observation.FrozenSnapshot`**s (before/after a tick) and pass them to
   **`observation.diff_snapshots`**, which infers `piece_arrived`/`piece_captured`/
   `promotion`/`game_over` from what changed.
7. **`scripting.ScriptRunner`** is a text-command interpreter (`click x y` / `jump x y` /
   `wait ms` / `print board`) built on top of steps 3–6, used by the integration tests and
   available for any future CLI/replay tooling.

## Two invariants worth knowing before you touch `model/` or `realtime/`

**`Piece` owns its own state transitions.** `PieceState` (IDLE/MOVING/JUMPING/COOLING/
CAPTURED) is never set with a raw `piece.state = PieceState.X` outside `model/piece.py`
itself — every transition goes through a named method: `begin_move()`, `begin_jump()`,
`begin_cooldown()`, `settle_idle()`, `mark_captured()`. `model.Board` and
`realtime.RealTimeArbiter` both call these rather than assigning the field directly. Reading
`piece.state` directly is fine anywhere; *setting* it anywhere outside `piece.py` is the
thing to avoid re-introducing.

**`RealTimeArbiter` knows nothing about chess rules.** It resolves arrivals, jumps, and
cooldowns purely as physics/timing, and reports **every** capture via an
`on_piece_captured(piece)` callback — it has no concept of "royal" pieces or what ending the
game means. `GameEngine._on_piece_captured` is the one place that checks
`Piece.is_royal(piece.kind)` and sets `game_state.game_over = True`. If you're adding a new
"this kind of capture matters" rule, it belongs in `engine/`, not `realtime/`.

## Subpackage reference

| Subpackage | Owns | Depends on |
|---|---|---|
| `model/` | `Board` (grid + occupancy), `Piece`/`Color`/`Kind`/`PieceState`, `Position`, `GameState` | nothing |
| `rules/` | `RuleEngine.validate_move` + per-`Kind` `PieceRule` classes (`PIECE_RULES` registry) | `model` |
| `realtime/` | `RealTimeArbiter` (active motions/jumps/cooldowns, arrival resolution), `Motion`/`JumpMotion`/`CooldownTimer` | `model`, `config` |
| `engine/` | `GameEngine` (execute commands, `wait()`, king-capture decision, cooldown-ratio query), `MoveCommand`/`JumpCommand`/`CommandResult` | `model`, `rules`, `realtime`, `config` |
| `interaction/` | `BoardMapper` (pixel↔`Position`), `Controller` (click/jump selection state machine → commands) | `model`, `engine` |
| `io/` | `board_parser` (text→`Board`), `board_printer` (`Board`→text), `board_factory.standard_board()` | `model` |
| `observation/` | `FrozenSnapshot`, `diff_snapshots` | `model` |
| `scripting/` | `ScriptRunner` (text-script interpreter) | `engine`, `interaction`, `io` |
| `engine_builder.py` | `build_engine()`, `build_script_runner()` — the composition root for this package | everything above |
| `config.py` | Shared constants: `CELL_SIZE_PX`, `PIECE_SPEED_PPS`, `JUMP_DURATION_MS`, `COOLDOWN_MS` | nothing |

## Testing

`tests/unit/` mirrors this subpackage layout one file per package (`test_model.py`,
`test_engine.py`, `test_rules.py`, `test_realtime.py`, `test_interaction.py`, `test_io.py`,
`test_snapshot_diff.py`); `tests/integration/test_script_runner.py` exercises the full stack
end to end. `tests/conftest.py` provides `W(kind, row, col)`/`B(kind, row, col)` piece
builders and `board_with(*pieces)`/`empty_board()` used throughout.
