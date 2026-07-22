"""
Unit tests for UI/state/observer.py's Subject pub/sub.
"""
from state.observer import Subject


def test_publish_with_no_subscribers_does_not_raise():
    subject = Subject()
    subject.publish('event')  # must not raise


def test_subscriber_receives_published_event():
    subject = Subject()
    received = []
    subject.subscribe(received.append)

    subject.publish('hello')

    assert received == ['hello']


def test_multiple_subscribers_all_receive_the_event():
    subject = Subject()
    received_a, received_b = [], []
    subject.subscribe(received_a.append)
    subject.subscribe(received_b.append)

    subject.publish('hello')

    assert received_a == ['hello']
    assert received_b == ['hello']


def test_subscribers_are_notified_in_subscription_order():
    subject = Subject()
    order = []
    subject.subscribe(lambda e: order.append('first'))
    subject.subscribe(lambda e: order.append('second'))

    subject.publish('event')

    assert order == ['first', 'second']


def test_a_raising_subscriber_does_not_prevent_others_from_being_notified():
    subject = Subject()
    received = []

    def broken(event):
        raise ValueError('boom')

    subject.subscribe(broken)
    subject.subscribe(received.append)

    subject.publish('hello')  # must not raise

    assert received == ['hello']


def test_multiple_publishes_each_reach_the_subscriber():
    subject = Subject()
    received = []
    subject.subscribe(received.append)

    subject.publish('a')
    subject.publish('b')

    assert received == ['a', 'b']
