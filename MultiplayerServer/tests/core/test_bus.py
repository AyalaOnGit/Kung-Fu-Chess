import asyncio

import pytest

from core.bus import AsyncMessageBus


async def _wait_for(event: asyncio.Event, timeout: float = 1.0) -> None:
    await asyncio.wait_for(event.wait(), timeout=timeout)


@pytest.mark.asyncio
async def test_subscriber_receives_published_event():
    bus = AsyncMessageBus()
    received = []
    got_it = asyncio.Event()

    async def handler(event):
        received.append(event)
        got_it.set()

    unsubscribe = bus.subscribe('room:1', handler)
    try:
        bus.publish('room:1', {'kind': 'move'})
        await _wait_for(got_it)
        assert received == [{'kind': 'move'}]
    finally:
        unsubscribe()


@pytest.mark.asyncio
async def test_multiple_subscribers_on_same_topic_all_receive():
    bus = AsyncMessageBus()
    first_received = asyncio.Event()
    second_received = asyncio.Event()

    async def first(event):
        first_received.set()

    async def second(event):
        second_received.set()

    unsubscribe_first = bus.subscribe('room:1', first)
    unsubscribe_second = bus.subscribe('room:1', second)
    try:
        bus.publish('room:1', 'ping')
        await _wait_for(first_received)
        await _wait_for(second_received)
    finally:
        unsubscribe_first()
        unsubscribe_second()


@pytest.mark.asyncio
async def test_publish_to_topic_with_no_subscribers_does_not_raise():
    bus = AsyncMessageBus()
    bus.publish('nobody:listening', 'x')
    # give the event loop a turn; nothing should blow up
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_subscriber_only_receives_events_for_its_own_topic():
    bus = AsyncMessageBus()
    received = []
    got_it = asyncio.Event()

    async def handler(event):
        received.append(event)
        got_it.set()

    unsubscribe = bus.subscribe('room:1', handler)
    try:
        bus.publish('room:2', 'not for you')
        bus.publish('room:1', 'for you')
        await _wait_for(got_it)
        assert received == ['for you']
    finally:
        unsubscribe()


@pytest.mark.asyncio
async def test_unsubscribe_stops_future_delivery():
    bus = AsyncMessageBus()
    received = []
    got_first = asyncio.Event()

    async def handler(event):
        received.append(event)
        got_first.set()

    unsubscribe = bus.subscribe('room:1', handler)
    bus.publish('room:1', 'first')
    await _wait_for(got_first)

    unsubscribe()
    bus.publish('room:1', 'second')
    await asyncio.sleep(0.05)  # let any (unwanted) delivery happen

    assert received == ['first']


@pytest.mark.asyncio
async def test_unsubscribe_is_idempotent():
    bus = AsyncMessageBus()

    async def handler(event):
        pass

    unsubscribe = bus.subscribe('room:1', handler)
    unsubscribe()
    unsubscribe()  # must not raise


@pytest.mark.asyncio
async def test_unsubscribe_cancels_a_handler_mid_flight_cleanly():
    """unsubscribe() cancels the consumer task outright, even while it's
    in the middle of awaiting a slow handler -- _consume's own
    `except asyncio.CancelledError: raise` (as opposed to the bare
    `except Exception` below it) must let that cancellation keep
    propagating rather than swallowing it like any other handler error."""
    bus = AsyncMessageBus()
    handler_started = asyncio.Event()

    async def slow_handler(event):
        handler_started.set()
        await asyncio.sleep(10)  # never completes on its own

    unsubscribe = bus.subscribe('room:1', slow_handler)
    task = bus._subscriptions['room:1'][0].task
    bus.publish('room:1', 'x')
    await _wait_for(handler_started)

    unsubscribe()  # cancels the task while it's inside slow_handler's await
    await asyncio.sleep(0.05)  # let the cancellation actually propagate

    assert task.cancelled()
    assert bus._subscriptions == {}


@pytest.mark.asyncio
async def test_handler_exception_does_not_crash_bus_or_other_subscribers():
    bus = AsyncMessageBus()
    survivor_received = asyncio.Event()

    async def broken(event):
        raise RuntimeError('boom')

    async def survivor(event):
        survivor_received.set()

    unsubscribe_broken = bus.subscribe('room:1', broken)
    unsubscribe_survivor = bus.subscribe('room:1', survivor)
    try:
        bus.publish('room:1', 'x')
        await _wait_for(survivor_received)
    finally:
        unsubscribe_broken()
        unsubscribe_survivor()
