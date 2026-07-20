from core.clock import RealClock, FakeClock


def test_real_clock_returns_increasing_values():
    clock = RealClock()
    first = clock.now()
    second = clock.now()
    assert second >= first


def test_fake_clock_starts_at_given_value():
    clock = FakeClock(start=10.0)
    assert clock.now() == 10.0


def test_fake_clock_defaults_to_zero():
    clock = FakeClock()
    assert clock.now() == 0.0


def test_fake_clock_advance_accumulates():
    clock = FakeClock(start=0.0)
    clock.advance(5)
    clock.advance(2.5)
    assert clock.now() == 7.5


def test_fake_clock_does_not_advance_on_its_own():
    clock = FakeClock(start=3.0)
    assert clock.now() == 3.0
    assert clock.now() == 3.0
