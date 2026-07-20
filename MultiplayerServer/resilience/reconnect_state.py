"""
ReconnectState: pure, Clock-injected tracking of room participants who
disconnected mid-game (§4.1) — no asyncio anywhere in this file.
resilience/reconnect_loop.py is the only async code in this package; it
polls expire() roughly once a second.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core.clock import Clock
from network.session import Role

DEFAULT_GRACE_SECONDS = 25.0


@dataclass(frozen=True)
class _Entry:
    user_id: int
    role: Role
    room_id: str
    disconnected_at: float


class ReconnectState:
    def __init__(self, clock: Clock, grace_seconds: float = DEFAULT_GRACE_SECONDS):
        self._clock = clock
        self._grace_seconds = grace_seconds
        self._entries: Dict[int, _Entry] = {}

    def mark_disconnected(self, user_id: int, role: Role, room_id: str) -> None:
        self._entries[user_id] = _Entry(
            user_id=user_id, role=role, room_id=room_id, disconnected_at=self._clock.now(),
        )

    def reclaim(self, user_id: int) -> Optional[Tuple[Role, str]]:
        """Pop and return (role, room_id) a reconnecting user_id held, or
        None if there was no pending entry (never disconnected, or already
        expired)."""
        entry = self._entries.pop(user_id, None)
        return (entry.role, entry.room_id) if entry is not None else None

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, user_id: int) -> bool:
        return user_id in self._entries

    def expire(self, now: float) -> List[Tuple[int, Role, str]]:
        """Remove and return (user_id, role, room_id) for anyone past their grace period."""
        expired = [(e.user_id, e.role, e.room_id) for e in self._entries.values()
                   if now - e.disconnected_at >= self._grace_seconds]
        for user_id, _role, _room_id in expired:
            del self._entries[user_id]
        return expired
