from __future__ import annotations
import time
from typing import Protocol


class Clock(Protocol):
    """The single time source for the whole server. now() -> seconds."""

    def now(self) -> float: ...


class RealClock:
    """Production clock backed by a monotonic counter."""

    def now(self) -> float:
        return time.monotonic()


class FakeClock:
    """Test clock: starts at a fixed value, advances only when told to."""

    def __init__(self, start: float = 0.0):
        self._now = start

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds
