from core.clock import FakeClock
from matchmaking.queue import MatchmakingQueue


def test_queue_entry_expires_after_60_seconds():
    clock = FakeClock(start=0.0)
    queue = MatchmakingQueue(clock=clock)
    queue.enqueue(user_id=1, elo=1200)

    assert queue.expire(clock.now()) == []  # not yet expired

    clock.advance(61)
    assert queue.expire(clock.now()) == [1]  # instantly "60 seconds" later


def test_expire_leaves_non_expired_entries_queued():
    clock = FakeClock(start=0.0)
    queue = MatchmakingQueue(clock=clock, timeout_seconds=60)
    queue.enqueue(user_id=1, elo=1200)
    clock.advance(30)
    queue.enqueue(user_id=2, elo=1200)  # joins later, not expired yet

    clock.advance(31)  # user 1 now at 61s, user 2 at 31s
    assert queue.expire(clock.now()) == [1]
    assert 2 in queue
    assert 1 not in queue


def test_expire_returns_multiple_in_join_order():
    clock = FakeClock(start=0.0)
    queue = MatchmakingQueue(clock=clock, timeout_seconds=10)
    queue.enqueue(user_id=1, elo=1200)
    clock.advance(1)
    queue.enqueue(user_id=2, elo=1200)

    clock.advance(20)
    assert queue.expire(clock.now()) == [1, 2]
    assert len(queue) == 0


def test_dequeue_removes_a_queued_user_and_reports_it_was_there():
    clock = FakeClock()
    queue = MatchmakingQueue(clock=clock)
    queue.enqueue(user_id=1, elo=1200)

    assert queue.dequeue(1) is True
    assert 1 not in queue
    assert queue.dequeue(1) is False  # already gone


def test_reenqueue_resets_join_time():
    clock = FakeClock(start=0.0)
    queue = MatchmakingQueue(clock=clock, timeout_seconds=60)
    queue.enqueue(user_id=1, elo=1200)

    clock.advance(50)
    queue.enqueue(user_id=1, elo=1200)  # re-join resets the clock

    clock.advance(50)  # 50s since re-join, 100s since original join
    assert queue.expire(clock.now()) == []  # would have expired under the old join time

    clock.advance(11)
    assert queue.expire(clock.now()) == [1]


def test_elo_range_exposes_the_configured_value():
    queue = MatchmakingQueue(clock=FakeClock(), elo_range=150)

    assert queue.elo_range == 150


def test_find_pairings_pairs_entries_within_elo_range():
    clock = FakeClock()
    queue = MatchmakingQueue(clock=clock, elo_range=100)
    queue.enqueue(user_id=1, elo=1200)
    queue.enqueue(user_id=2, elo=1250)

    pairs = queue.find_pairings(clock.now())

    assert pairs == [(1, 2)]
    assert len(queue) == 0


def test_find_pairings_does_not_pair_entries_outside_elo_range():
    clock = FakeClock()
    queue = MatchmakingQueue(clock=clock, elo_range=100)
    queue.enqueue(user_id=1, elo=1200)
    queue.enqueue(user_id=2, elo=1400)

    pairs = queue.find_pairings(clock.now())

    assert pairs == []
    assert len(queue) == 2


def test_find_pairings_leaves_an_odd_one_out_queued():
    clock = FakeClock()
    queue = MatchmakingQueue(clock=clock, elo_range=100)
    queue.enqueue(user_id=1, elo=1200)
    queue.enqueue(user_id=2, elo=1200)
    queue.enqueue(user_id=3, elo=1200)

    pairs = queue.find_pairings(clock.now())

    assert len(pairs) == 1
    assert len(queue) == 1


def test_find_pairings_prefers_earliest_joiners():
    clock = FakeClock(start=0.0)
    queue = MatchmakingQueue(clock=clock, elo_range=1000)  # wide range: eligibility isn't the constraint here
    queue.enqueue(user_id=1, elo=1200)
    clock.advance(1)
    queue.enqueue(user_id=2, elo=1200)
    clock.advance(1)
    queue.enqueue(user_id=3, elo=1200)

    pairs = queue.find_pairings(clock.now())

    assert pairs == [(1, 2)]
    assert 3 in queue


def test_find_pairings_each_user_appears_in_at_most_one_pairing():
    clock = FakeClock()
    queue = MatchmakingQueue(clock=clock, elo_range=1000)
    for user_id in (1, 2, 3, 4):
        queue.enqueue(user_id=user_id, elo=1200)

    pairs = queue.find_pairings(clock.now())

    paired_ids = [uid for pair in pairs for uid in pair]
    assert len(paired_ids) == len(set(paired_ids))
    assert len(pairs) == 2
    assert len(queue) == 0


def test_find_pairings_skips_a_candidate_already_claimed_by_an_earlier_pairing():
    """The inner loop's own `if other.user_id in paired_ids: continue` --
    distinct from the outer loop's identical-looking skip just above it --
    fires when a later-joined candidate was already claimed by an earlier
    entry's pairing before this entry gets its own turn to scan for a
    partner. Join order: 1 (elo 1000), 2 (elo 1200), 3 (elo 1010), 4 (elo
    1200); elo_range=50. Entry 1 pairs with 3 (only one in range). Entry 2
    then scans [3, 4]: 3 is already claimed (hits the inner `continue`),
    so it falls through to 4."""
    clock = FakeClock(start=0.0)
    queue = MatchmakingQueue(clock=clock, elo_range=50)
    queue.enqueue(user_id=1, elo=1000)
    clock.advance(1)
    queue.enqueue(user_id=2, elo=1200)
    clock.advance(1)
    queue.enqueue(user_id=3, elo=1010)
    clock.advance(1)
    queue.enqueue(user_id=4, elo=1200)

    pairs = queue.find_pairings(clock.now())

    assert set(pairs) == {(1, 3), (2, 4)}
    assert len(queue) == 0


def test_find_pairings_respects_max_pairs():
    clock = FakeClock()
    queue = MatchmakingQueue(clock=clock, elo_range=1000)
    for user_id in (1, 2, 3, 4):
        queue.enqueue(user_id=user_id, elo=1200)

    pairs = queue.find_pairings(clock.now(), max_pairs=1)

    assert pairs == [(1, 2)]
    assert len(queue) == 2  # 3 and 4 stay queued for the next poll
    assert 3 in queue and 4 in queue
