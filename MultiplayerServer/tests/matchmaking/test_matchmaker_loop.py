import asyncio

import pytest

from core.clock import FakeClock
from matchmaking.matchmaker_loop import MatchmakerLoop
from matchmaking.queue import MatchmakingQueue


async def _noop_paired(_white_id, _black_id):
    pass


async def _noop_timeout(_user_id):
    pass


def _loop(queue=None, clock=None, on_paired=_noop_paired, on_timeout=_noop_timeout,
          poll_interval_seconds=0.02):
    clock = clock or FakeClock()
    queue = queue if queue is not None else MatchmakingQueue(clock=clock)
    return MatchmakerLoop(queue, clock, on_paired, on_timeout, poll_interval_seconds)


async def _poll_until(predicate, attempts=75, interval=0.02):
    for _ in range(attempts):
        if predicate():
            return
        await asyncio.sleep(interval)


# --- lifecycle (mirrors game/rooms.py's Room tests) ---

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


# --- pairing / timeout behavior ---

@pytest.mark.asyncio
async def test_pairs_two_queued_players_within_elo_range():
    clock = FakeClock()
    queue = MatchmakingQueue(clock=clock, elo_range=100)
    queue.enqueue(user_id=1, elo=1200)
    queue.enqueue(user_id=2, elo=1250)

    paired = []

    async def on_paired(white_id, black_id):
        paired.append((white_id, black_id))

    loop = _loop(queue=queue, clock=clock, on_paired=on_paired)
    try:
        loop.start()
        await _poll_until(lambda: paired)
    finally:
        await loop.stop()

    assert paired == [(1, 2)]
    assert len(queue) == 0


@pytest.mark.asyncio
async def test_pairs_multiple_groups_concurrently_in_one_poll():
    # Phase 5 removed the Phase 1-4 single-match-slot limit (game/rooms.py
    # supports many concurrent rooms), so a poll with two eligible pairs
    # queued should pair both, not just one.
    clock = FakeClock()
    queue = MatchmakingQueue(clock=clock, elo_range=1000)
    for user_id in (1, 2, 3, 4):
        queue.enqueue(user_id=user_id, elo=1200)

    paired = []

    async def on_paired(white_id, black_id):
        paired.append((white_id, black_id))

    loop = _loop(queue=queue, clock=clock, on_paired=on_paired)
    try:
        loop.start()
        await _poll_until(lambda: len(paired) == 2)
    finally:
        await loop.stop()

    assert len(paired) == 2
    assert len(queue) == 0


@pytest.mark.asyncio
async def test_notifies_timeout_for_expired_entries():
    clock = FakeClock(start=0.0)
    queue = MatchmakingQueue(clock=clock, timeout_seconds=60)
    queue.enqueue(user_id=1, elo=1200)

    timed_out = []

    async def on_timeout(user_id):
        timed_out.append(user_id)

    loop = _loop(queue=queue, clock=clock, on_timeout=on_timeout)
    try:
        loop.start()
        await asyncio.sleep(0.05)
        assert timed_out == []  # clock hasn't moved — not expired yet

        clock.advance(61)
        await _poll_until(lambda: timed_out)
    finally:
        await loop.stop()

    assert timed_out == [1]


@pytest.mark.asyncio
async def test_on_paired_exception_does_not_crash_the_loop():
    clock = FakeClock()
    queue = MatchmakingQueue(clock=clock, elo_range=1000, timeout_seconds=60)
    queue.enqueue(user_id=1, elo=1200)
    queue.enqueue(user_id=2, elo=1200)

    async def on_paired(_white_id, _black_id):
        raise RuntimeError('boom')

    survived = []

    async def on_timeout(user_id):
        survived.append(user_id)

    loop = _loop(queue=queue, clock=clock, on_paired=on_paired, on_timeout=on_timeout)
    try:
        loop.start()
        await asyncio.sleep(0.1)  # let the pairing attempt (and its exception) happen

        # Prove the loop is still alive afterward: enqueue someone new and
        # let them time out.
        queue.enqueue(user_id=3, elo=1200)
        clock.advance(61)
        await _poll_until(lambda: survived)
    finally:
        await loop.stop()

    assert survived == [3]
