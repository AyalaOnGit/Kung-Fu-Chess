# rating/

Standard ELO rating math. Pure functions, no I/O, no clock — the smallest subpackage in
this codebase by design.

## Files

- **`elo.py`**:
  - `expected_score(rating_a, rating_b) -> float` — probability that a player rated
    `rating_a` beats one rated `rating_b`.
  - `update_ratings(white_elo, black_elo, *, white_score) -> (new_white_elo, new_black_elo)`
    — `white_score` is `1.0`/`0.0`/`0.5` for a white win/loss/draw; `K_FACTOR = 32`. Both
    results are rounded to the nearest int.

## Data flow

`game/rating_service.py` is the only caller: it reads both players' current ELO from
`db/users_repository.py`, calls `update_ratings(...)`, persists the new values back via
`UsersRepository.update_elo` and a `MatchesRepository.record_result` row, and returns the
before/after deltas for the `rating_update` envelope sent to both clients.

## Depends on

Nothing else in this repo.
