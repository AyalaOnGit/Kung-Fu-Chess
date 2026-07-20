"""pbkdf2 hash/verify — pure functions, no I/O."""
from __future__ import annotations
import hashlib
import hmac
import os
from typing import Optional, Tuple

_ALGORITHM = 'sha256'
_ITERATIONS = 200_000
_SALT_BYTES = 16


def hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
    """Return (hash_hex, salt_hex). Generates a fresh random salt if none is given."""
    if salt is None:
        salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(_ALGORITHM, password.encode('utf-8'), salt, _ITERATIONS)
    return digest.hex(), salt.hex()


def verify_password(password: str, hash_hex: str, salt_hex: str) -> bool:
    """Constant-time comparison — avoids leaking match/mismatch via timing."""
    candidate_hash, _ = hash_password(password, salt=bytes.fromhex(salt_hex))
    return hmac.compare_digest(candidate_hash, hash_hex)
