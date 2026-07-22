"""
MatchmakingQueue: plain data structure + pure methods — no asyncio
anywhere in this file (§4.1). matchmaking/matchmaker_loop.py is the only
async code in this package; it polls these methods roughly once a second.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple

from core.clock import Clock

DEFAULT_ELO_RANGE = 100
DEFAULT_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True)
class _Entry:
    user_id: int
    elo: int
    joined_at: float


class MatchmakingQueue:
    def __init__(self, clock: Clock, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
                 elo_range: int = DEFAULT_ELO_RANGE):
        self._clock = clock
        self._timeout_seconds = timeout_seconds
        self._elo_range = elo_range
        self._entries: List[_Entry] = []

    @property
    def elo_range(self) -> int:
        return self._elo_range

    def enqueue(self, user_id: int, elo: int) -> None:
        """Add user_id to the queue. Re-enqueuing resets their join time."""
        self.dequeue(user_id)
        self._entries.append(_Entry(user_id=user_id, elo=elo, joined_at=self._clock.now()))

    def dequeue(self, user_id: int) -> bool:
        """Remove user_id if present. Returns True if it was actually queued."""
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.user_id != user_id]
        return len(self._entries) != before

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, user_id: int) -> bool:
        return any(e.user_id == user_id for e in self._entries)

    def find_pairings(self, now: float, max_pairs: Optional[int] = None) -> List[Tuple[int, int]]:
        """
        Pair up waiting entries within elo_range of each other, earliest
        joiners first; each user_id appears in at most one pairing this
        call. Paired entries are removed from the queue; unpaired entries
        stay queued for the next call.

        :param max_pairs: stop once this many pairs have been formed (a
            caller with only one match slot passes 1) — a value of None
            forms as many pairs as the queue allows.
        """
        ordered = sorted(self._entries, key=lambda e: e.joined_at)
        paired_ids: set = set()
        pairs: List[Tuple[int, int]] = []

        for i, entry in enumerate(ordered):
            if max_pairs is not None and len(pairs) >= max_pairs:
                break
            if entry.user_id in paired_ids:
                continue
            for other in ordered[i + 1:]:
                if other.user_id in paired_ids:
                    continue
                if abs(entry.elo - other.elo) <= self._elo_range:
                    pairs.append((entry.user_id, other.user_id))
                    paired_ids.update((entry.user_id, other.user_id))
                    break

        if paired_ids:
            self._entries = [e for e in self._entries if e.user_id not in paired_ids]
        return pairs

    def expire(self, now: float) -> List[int]:
        """Remove and return user_ids queued for at least timeout_seconds as of now,
        in join order."""
        expired = [e.user_id for e in self._entries if now - e.joined_at >= self._timeout_seconds]
        if expired:
            expired_set = set(expired)
            self._entries = [e for e in self._entries if e.user_id not in expired_set]
        return expired
