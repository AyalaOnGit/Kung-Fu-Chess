"""
Unit tests for UI/user_input/mouse_controller.py's click/double-click state
machine (see the module docstring for the state diagram).
"""
from vendor.img import MouseEventType
from user_input.mouse_controller import MouseController


def _controller(click_result=False):
    clicks = []
    jumps = []
    clock_state = {'now_ms': 0.0}

    def click_handler(x, y):
        clicks.append((x, y))
        return click_result

    def jump_handler(x, y):
        jumps.append((x, y))

    controller = MouseController(click_handler, jump_handler, clock=lambda: clock_state['now_ms'] / 1000.0)
    return controller, clicks, jumps, clock_state


def _fire(controller, clock_state, event, x, y, now_ms):
    clock_state['now_ms'] = now_ms
    controller.on_mouse_event(event, x, y, 0, None)


def test_first_click_calls_click_handler_as_a_selection():
    controller, clicks, jumps, clock_state = _controller(click_result=False)

    _fire(controller, clock_state, MouseEventType.LEFT_DOWN, 10, 10, now_ms=0)

    assert clicks == [(10, 10)]
    assert jumps == []


def test_second_click_same_spot_within_window_triggers_jump_not_click():
    controller, clicks, jumps, clock_state = _controller(click_result=False)

    _fire(controller, clock_state, MouseEventType.LEFT_DOWN, 10, 10, now_ms=0)
    _fire(controller, clock_state, MouseEventType.LEFT_DOWN, 10, 10, now_ms=100)

    assert clicks == [(10, 10)]  # only the first click reached click_handler
    assert jumps == [(10, 10)]


def test_second_click_same_spot_after_window_is_a_fresh_selection():
    controller, clicks, jumps, clock_state = _controller(click_result=False)

    _fire(controller, clock_state, MouseEventType.LEFT_DOWN, 10, 10, now_ms=0)
    _fire(controller, clock_state, MouseEventType.LEFT_DOWN, 10, 10, now_ms=500)  # past DOUBLE_CLICK_MS=300

    assert clicks == [(10, 10), (10, 10)]
    assert jumps == []


def test_second_click_different_spot_is_treated_as_a_move_attempt():
    controller, clicks, jumps, clock_state = _controller(click_result=False)

    _fire(controller, clock_state, MouseEventType.LEFT_DOWN, 10, 10, now_ms=0)
    _fire(controller, clock_state, MouseEventType.LEFT_DOWN, 200, 200, now_ms=50)

    assert clicks == [(10, 10), (200, 200)]
    assert jumps == []


def test_completed_move_click_resets_so_next_click_starts_fresh():
    """When click_handler reports a destination click (src->dst attempt),
    the double-click timer must fully reset -- a fast click right after on
    the same cell must not be misread as part of the old sequence."""
    controller, clicks, jumps, clock_state = _controller(click_result=True)

    _fire(controller, clock_state, MouseEventType.LEFT_DOWN, 10, 10, now_ms=0)
    assert clicks == [(10, 10)]

    _fire(controller, clock_state, MouseEventType.LEFT_DOWN, 10, 10, now_ms=50)

    # Reset() happened after the first click (click_result=True), so this
    # is read as a brand new selection, not a same-spot double-click.
    assert clicks == [(10, 10), (10, 10)]
    assert jumps == []


def test_native_double_click_event_triggers_jump_directly():
    controller, clicks, jumps, clock_state = _controller()

    _fire(controller, clock_state, MouseEventType.LEFT_DBLCLK, 42, 42, now_ms=0)

    assert jumps == [(42, 42)]
    assert clicks == []


def test_native_double_click_with_no_jump_handler_does_not_raise():
    clock_state = {'now_ms': 0.0}
    controller = MouseController(click_handler=lambda x, y: False, jump_handler=None,
                                  clock=lambda: clock_state['now_ms'] / 1000.0)
    _fire(controller, clock_state, MouseEventType.LEFT_DBLCLK, 1, 1, now_ms=0)  # must not raise


def test_other_events_are_ignored():
    controller, clicks, jumps, clock_state = _controller()

    _fire(controller, clock_state, MouseEventType.MOVE, 5, 5, now_ms=0)

    assert clicks == []
    assert jumps == []


def test_double_click_outside_radius_is_not_a_jump():
    controller, clicks, jumps, clock_state = _controller(click_result=False)

    _fire(controller, clock_state, MouseEventType.LEFT_DOWN, 10, 10, now_ms=0)
    _fire(controller, clock_state, MouseEventType.LEFT_DOWN, 100, 100, now_ms=50)  # far away, still fast

    assert clicks == [(10, 10), (100, 100)]
    assert jumps == []


def test_clock_defaults_to_real_time_monotonic():
    """No clock override: the default parameter is the real time.monotonic,
    so a real click just works without needing any injection."""
    clicks = []
    controller = MouseController(lambda x, y: clicks.append((x, y)) or False)
    controller.on_mouse_event(MouseEventType.LEFT_DOWN, 7, 7, 0, None)
    assert clicks == [(7, 7)]


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
