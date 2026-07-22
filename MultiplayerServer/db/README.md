# db/

sqlite3 persistence: user accounts (with ELO) and finished-match history. Repository
Pattern throughout — every caller talks to `UsersRepository`/`MatchesRepository`, never to
raw SQL or a `sqlite3.Connection`.

## Files

- **`connection.py`** — `Database`: owns one `sqlite3.Connection` and a dedicated
  single-worker `ThreadPoolExecutor`. `sqlite3.Connection`s may only be used from the thread
  that created them; a plain `asyncio.to_thread` can hop to a *different* worker on every
  call via the loop's shared default executor, so `Database.run(fn)` always dispatches to
  its own one dedicated thread instead, connecting lazily on first use. This also gives free
  serialization of concurrent repository calls with no extra lock.
- **`schema.py`** — `init_schema(conn)`: idempotent `CREATE TABLE IF NOT EXISTS` for `users`
  (username, password hash+salt, `elo` defaulting to 1200) and `matches` (both players,
  winner, result reason, ELO before/after for both sides). Safe to call every startup.
- **`users_repository.py`** — `UsersRepository(db)`: `create`, `get_by_username`, `get_by_id`,
  `update_elo`. Returns/accepts the frozen `UserRecord` dataclass, never a raw `sqlite3.Row`.
- **`matches_repository.py`** — `MatchesRepository(db)`: `record_result(...)` inserts one
  finished-match row and returns its id.

## Data flow

`main.py` constructs one `Database` and both repositories at startup and injects them
everywhere they're needed: `auth/service.py` (registration/login) and
`game/rating_service.py` (recording a finished match's ELO change) are the two real
consumers. Nothing else in this codebase touches `db/` directly.

## Depends on

Nothing else in this repo — `db/` is a leaf package (stdlib `sqlite3` + `asyncio` only).
