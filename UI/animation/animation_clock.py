"""
Performance-counter based animation clock.

Provides delta-time measurements for smooth animation independent of frame rate.
"""
from __future__ import annotations
import time
from typing import Callable, Optional


class AnimationClock:
    """
    Tracks elapsed time using perf_counter for consistent animation timing.
    
    Responsibilities:
      - Measure time delta (dt) between frames
      - Allow injection of mock time source for testing
      - Optionally cap frame rate
    """
    
    def __init__(self, time_source: Optional[Callable[[], float]] = None):
        """
        Initialize the clock.
        
        :param time_source: optional callable returning current time in seconds.
                           defaults to time.perf_counter
        """
        self._time_source = time_source or time.perf_counter
        self._last_time = self._time_source()
    
    def tick(self) -> float:
        """
        Advance time and return delta in milliseconds.
        
        :return: milliseconds elapsed since last tick (or init)
        """
        now = self._time_source()
        dt_ms = (now - self._last_time) * 1000
        self._last_time = now
        return dt_ms
    
    def reset(self) -> None:
        """Reset the clock to current time."""
        self._last_time = self._time_source()
