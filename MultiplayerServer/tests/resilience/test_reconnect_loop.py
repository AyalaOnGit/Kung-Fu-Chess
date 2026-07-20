import asyncio

import pytest

from core.clock import FakeClock
from network.session import Role
from resilience.reconnect_loop import ReconnectLoop
from resilience.reconnect_state import ReconnectState


async def _noop_expired(_user_id, _role, _room_id):
    pass


def _loop(state=None, clock=None, on_expired=_noop_expired, poll_interval_seconds=0.02):
    clock = clock or FakeClock()
    state = state if state is not None else ReconnectState(clock=clock, grace_seconds=25)
    return ReconnectLoop(state, clock, on_expired, poll_interval_seconds)


async def _poll_until(predicate, attempts=75, interval=0.02):
    for _ in range(attempts):
        if predicate():
            return
        await asyncio.sleep(interval)


# --- lifecycle (same shape as Room / MatchmakerLoop) ---

@pytest.mark.asyncio
async def test_start_marks_the_loop_running():
    loop = _loop()
    loop.start()
    try:
        assert loop.is_running
    finally:
        await loop.stop()


@pytest.mark.asyncio
async def test_starting_twice_raises():
    loop = _loop()
    loop.start()
    try:
        with pytest.raises(RuntimeError):
            loop.start()
    finally:
        await loop.stop()


@pytest.mark.asyncio
async def test_stop_without_start_is_a_noop():
    loop = _loop()
    await loop.stop()
    assert not loop.is_running


@pytest.mark.asyncio
async def test_stop_is_idempotent():
    loop = _loop()
    loop.start()
    await loop.stop()
    await loop.stop()
    assert not loop.is_running


@pytest.mark.asyncio
async def test_stop_leaves_no_lingering_task():
    loop = _loop()
    tasks_before = asyncio.all_tasks()
    loop.start()
    await asyncio.sleep(0.03)
    assert asyncio.all_tasks() - tasks_before

    await loop.stop()
    await asyncio.sleep(0)
    assert asyncio.all_tasks() - tasks_before == set()


# --- expiry behavior ---

@pytest.mark.asyncio
async def test_notifies_on_expiry_with_user_id_role_and_room_id():
    clock = FakeClock(start=0.0)
    state = ReconnectState(clock=clock, grace_seconds=25)
    state.mark_disconnected(user_id=7, role=Role.BLACK, room_id='room-a')

    expired = []

    async def on_expired(user_id, role, room_id):
        expired.append((user_id, role, room_id))

    loop = _loop(state=state, clock=clock, on_expired=on_expired)
    try:
        loop.start()
        await asyncio.sleep(0.05)
        assert expired == []  # clock hasn't moved

        clock.advance(26)
        await _poll_until(lambda: expired)
    finally:
        await loop.stop()

    assert expired == [(7, Role.BLACK, 'room-a')]


@pytest.mark.asyncio
async def test_reconnecting_before_expiry_means_no_notification():
    clock = FakeClock(start=0.0)
    state = ReconnectState(clock=clock, grace_seconds=25)
    state.mark_disconnected(user_id=1, role=Role.WHITE, room_id='room-a')

    expired = []

    async def on_expired(user_id, role, room_id):
        expired.append((user_id, role, room_id))

    loop = _loop(state=state, clock=clock, on_expired=on_expired)
    try:
        loop.start()
        state.reclaim(1)  # reconnected before any poll saw it expire
        clock.advance(26)
        await asyncio.sleep(0.1)  # several polls' worth
    finally:
        await loop.stop()

    assert expired == []


@pytest.mark.asyncio
async def test_on_expired_exception_does_not_crash_the_loop():
    clock = FakeClock(start=0.0)
    state = ReconnectState(clock=clock, grace_seconds=25)
    state.mark_disconnected(user_id=1, role=Role.WHITE, room_id='room-a')

    survived = []

    async def on_expired(user_id, role, room_id):
        if user_id == 1:
            raise RuntimeError('boom')
        survived.append((user_id, role, room_id))

    loop = _loop(state=state, clock=clock, on_expired=on_expired)
    try:
        loop.start()
        clock.advance(26)
        await asyncio.sleep(0.1)  # let the failing callback run

        # Prove the loop is still alive afterward: a second entry still
        # gets expired and reaches the callback normally.
        state.mark_disconnected(user_id=2, role=Role.BLACK, room_id='room-b')
        clock.advance(26)
        await _poll_until(lambda: survived)
    finally:
        await loop.stop()

    assert survived == [(2, Role.BLACK, 'room-b')]
