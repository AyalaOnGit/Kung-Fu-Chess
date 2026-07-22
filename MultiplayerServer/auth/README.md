# auth/

Registration and login orchestration.

## Files

- **`hashing.py`** — `hash_password(password, salt=None) -> (hash_hex, salt_hex)` and
  `verify_password(password, hash_hex, salt_hex) -> bool`. Pure functions, no I/O: PBKDF2-HMAC-SHA256,
  200,000 iterations, a fresh random 16-byte salt per password unless one is supplied (used by
  `verify_password` to recompute the hash for comparison). `verify_password` uses
  `hmac.compare_digest` for constant-time comparison, so a mistyped password can't be
  distinguished from a correct one via timing.
- **`service.py`** — `register(repo, username, password)` and `login(repo, username, password)`,
  both returning an `AuthResult(ok, user, error)`. `register` checks `UsersRepository` for an
  existing username first; `login` deliberately returns the *same* `'invalid_credentials'` error
  for "no such user" and "wrong password" — distinguishing them would let a client enumerate
  which usernames exist.

## Data flow

`network/dispatch.py`'s `register`/`login` command handlers call straight into this package,
then translate `AuthResult` into an outgoing `Envelope`. `AuthResult.error` is a plain string
(`'username_taken'` / `'invalid_credentials'`), not `core.protocol.ErrorCode` — this package has
no notion of the wire format; `dispatch.py` is the one place that maps the string onto an
`ErrorCode`.

## Depends on

`db/` (`UsersRepository`, `UserRecord`) only. Never imports `network/`, `core/`, or `kungfu_chess`.
