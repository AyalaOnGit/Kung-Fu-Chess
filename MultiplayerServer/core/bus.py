from __future__ import annotations
import asyncio
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable, DefaultDict, List

logger = logging.getLogger(__name__)

Handler = Callable[[Any], Awaitable[None]]
Unsubscribe = Callable[[], None]


class _Subscription:
    def __init__(self, queue: 'asyncio.Queue[Any]', task: 'asyncio.Task[None]'):
        self.queue = queue
        self.task = task


class AsyncMessageBus:
    """
    Topic-based async pub/sub.

    Each subscription owns one asyncio.Queue and one consumer task that
    drains it and awaits the handler. publish() never awaits a subscriber —
    it only enqueues, so a slow or stuck handler can't block the publisher.
    """

    def __init__(self):
        self._subscriptions: DefaultDict[str, List[_Subscription]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Handler) -> Unsubscribe:
        """Register handler for topic. Returns a callable that undoes it."""
        queue: 'asyncio.Queue[Any]' = asyncio.Queue()
        task = asyncio.create_task(self._consume(topic, queue, handler))
        subscription = _Subscription(queue, task)
        self._subscriptions[topic].append(subscription)

        unsubscribed = False

        def unsubscribe() -> None:
            nonlocal unsubscribed
            if unsubscribed:
                return
            unsubscribed = True
            task.cancel()
            subs = self._subscriptions.get(topic)
            if subs is not None and subscription in subs:
                subs.remove(subscription)
                if not subs:
                    del self._subscriptions[topic]

        return unsubscribe

    def publish(self, topic: str, event: Any) -> None:
        """Enqueue event for every current subscriber of topic. No-op if none."""
        for subscription in self._subscriptions.get(topic, ()):
            subscription.queue.put_nowait(event)

    async def _consume(self, topic: str, queue: 'asyncio.Queue[Any]', handler: Handler) -> None:
        while True:
            event = await queue.get()
            try:
                await handler(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Bus handler for topic %r raised", topic)
