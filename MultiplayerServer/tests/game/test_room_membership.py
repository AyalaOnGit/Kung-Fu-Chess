from game.room_membership import RoomMembership


def test_get_returns_none_none_for_unknown_room():
    membership = RoomMembership()
    assert membership.get('nope') == (None, None)


def test_add_then_get_returns_both_seats():
    membership = RoomMembership()
    membership.add('r1', 10, 20)
    assert membership.get('r1') == (10, 20)


def test_add_overwrites_existing_seats():
    membership = RoomMembership()
    membership.add('r1', 10, None)
    membership.add('r1', 10, 20)
    assert membership.get('r1') == (10, 20)


def test_remove_pops_and_returns_seats():
    membership = RoomMembership()
    membership.add('r1', 10, 20)

    seats = membership.remove('r1')

    assert seats == (10, 20)
    assert membership.get('r1') == (None, None)


def test_remove_unknown_room_returns_none_none():
    membership = RoomMembership()
    assert membership.remove('nope') == (None, None)


def test_rooms_are_independent():
    membership = RoomMembership()
    membership.add('r1', 1, 2)
    membership.add('r2', 3, 4)

    assert membership.get('r1') == (1, 2)
    assert membership.get('r2') == (3, 4)

    membership.remove('r1')
    assert membership.get('r2') == (3, 4)
