"""
register/login orchestration: calls hashing.py + users_repository.py only.

AuthResult.error is a plain string rather than core.protocol.ErrorCode —
this module stays decoupled from the wire layer; network/dispatch.py is
the one place that translates it into an outgoing Envelope.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from auth.hashing import hash_password, verify_password
from db.users_repository import UserRecord, UsersRepository


@dataclass(frozen=True)
class AuthResult:
    ok: bool
    user: Optional[UserRecord] = None
    error: Optional[str] = None  # 'username_taken' | 'invalid_credentials'


async def register(repo: UsersRepository, username: str, password: str) -> AuthResult:
    if await repo.get_by_username(username) is not None:
        return AuthResult(ok=False, error='username_taken')
    hash_hex, salt_hex = hash_password(password)
    user = await repo.create(username, hash_hex, salt_hex)
    return AuthResult(ok=True, user=user)


async def login(repo: UsersRepository, username: str, password: str) -> AuthResult:
    user = await repo.get_by_username(username)
    # Same error for "no such user" and "wrong password" — deliberately not
    # distinguishing them avoids letting a client enumerate valid usernames.
    if user is None or not verify_password(password, user.password_hash, user.password_salt):
        return AuthResult(ok=False, error='invalid_credentials')
    return AuthResult(ok=True, user=user)
