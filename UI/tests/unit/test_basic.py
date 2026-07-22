"""
Basic unit tests for UI modules.
"""
import pytest

from animation.animation_clock import AnimationClock
from animation.motion_predictor import interpolate_pixel, PixelMotion, is_motion_complete
from state.observer import Subject


def test_animation_clock():
    """Test animation clock timing."""
    sources = []
    
    def mock_time():
        return sources[0]
    
    sources.append(0.0)
    clock = AnimationClock(time_source=mock_time)
    
    sources[0] = 0.016  # 16ms later
    dt_ms = clock.tick()
    assert abs(dt_ms - 16) < 1, f"Expected ~16ms, got {dt_ms}"
    
    sources[0] = 0.032  # Another 16ms
    dt_ms = clock.tick()
    assert abs(dt_ms - 16) < 1, f"Expected ~16ms, got {dt_ms}"


def test_motion_predictor():
    """Test pixel interpolation."""
    motion = PixelMotion(
        src_px=(0, 0),
        dst_px=(100, 100),
        duration_ms=1000.0
    )
    
    # At 0ms, should be at source
    px = interpolate_pixel(motion, 0.0)
    assert px == (0, 0), f"Expected (0,0), got {px}"
    
    # At 500ms (halfway), should be near center
    px = interpolate_pixel(motion, 500.0)
    assert px == (50, 50), f"Expected (50,50), got {px}"
    
    # At 1000ms, should be at destination
    px = interpolate_pixel(motion, 1000.0)
    assert px == (100, 100), f"Expected (100,100), got {px}"
    
    # Past end, should clamp to destination
    px = interpolate_pixel(motion, 1500.0)
    assert px == (100, 100), f"Expected (100,100), got {px}"


def test_motion_complete():
    """Test motion completion check."""
    motion = PixelMotion(
        src_px=(0, 0),
        dst_px=(100, 0),
        duration_ms=500.0
    )
    
    assert not is_motion_complete(motion, 100.0)
    assert not is_motion_complete(motion, 499.0)
    assert is_motion_complete(motion, 500.0)
    assert is_motion_complete(motion, 1000.0)


def test_subject():
    """Test observer pattern."""
    subject = Subject()
    
    events = []
    
    def subscriber(event):
        events.append(event)
    
    subject.subscribe(subscriber)
    
    subject.publish("event1")
    subject.publish("event2")
    
    assert events == ["event1", "event2"], f"Expected ['event1', 'event2'], got {events}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
