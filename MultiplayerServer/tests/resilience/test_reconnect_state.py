from core.clock import FakeClock
from core.protocol import Role
from resilience.reconnect_state import ReconnectState


def test_mark_disconnected_then_reclaim_returns_the_role_and_room_id():
    state = ReconnectState(clock=FakeClock())
    state.mark_disconnected(user_id=1, role=Role.WHITE, room_id='room-a')

    assert 1 in state
    assert state.reclaim(1) == (Role.WHITE, 'room-a')
    assert 1 not in state


def test_reclaim_returns_none_when_never_disconnected():
    state = ReconnectState(clock=FakeClock())
    assert state.reclaim(999) is None


def test_reclaim_is_one_shot():
    state = ReconnectState(clock=FakeClock())
    state.mark_disconnected(user_id=1, role=Role.BLACK, room_id='room-a')

    assert state.reclaim(1) == (Role.BLACK, 'room-a')
    assert state.reclaim(1) is None  # already consumed


def test_entry_expires_after_the_grace_period():
    clock = FakeClock(start=0.0)
    state = ReconnectState(clock=clock, grace_seconds=25)
    state.mark_disconnected(user_id=1, role=Role.WHITE, room_id='room-a')

    assert state.expire(clock.now()) == []  # not yet

    clock.advance(26)
    assert state.expire(clock.now()) == [(1, Role.WHITE, 'room-a')]
    assert 1 not in state


def test_expire_leaves_non_expired_entries():
    clock = FakeClock(start=0.0)
    state = ReconnectState(clock=clock, grace_seconds=25)
    state.mark_disconnected(user_id=1, role=Role.WHITE, room_id='room-a')
    clock.advance(10)
    state.mark_disconnected(user_id=2, role=Role.BLACK, room_id='room-b')

    clock.advance(16)  # user 1 at 26s, user 2 at 16s
    assert state.expire(clock.now()) == [(1, Role.WHITE, 'room-a')]
    assert 2 in state
    assert 1 not in state


def test_reconnecting_before_expiry_prevents_it_from_ever_expiring():
    clock = FakeClock(start=0.0)
    state = ReconnectState(clock=clock, grace_seconds=25)
    state.mark_disconnected(user_id=1, role=Role.WHITE, room_id='room-a')

    clock.advance(10)
    assert state.reclaim(1) == (Role.WHITE, 'room-a')

    clock.advance(20)  # well past the original 25s grace period
    assert state.expire(clock.now()) == []


def test_different_users_can_be_disconnected_from_different_rooms_simultaneously():
    clock = FakeClock(start=0.0)
    state = ReconnectState(clock=clock, grace_seconds=25)
    state.mark_disconnected(user_id=1, role=Role.WHITE, room_id='room-a')
    state.mark_disconnected(user_id=2, role=Role.BLACK, room_id='room-b')

    assert state.reclaim(1) == (Role.WHITE, 'room-a')
    assert state.reclaim(2) == (Role.BLACK, 'room-b')
