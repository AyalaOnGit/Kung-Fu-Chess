"""
RoomMembership: tracks (white_user_id, black_user_id) per active room_id.

Both main.py's on_paired/on_game_over closures and network/dispatch.py's
create_room/join_room handlers need to read and write the same seats --
main.py's on_game_over docstring explains why this can't be re-derived
from SessionManager at game-over time (a disconnect-timeout loser has
already been removed from it by then). Previously threaded between the
two as a bare dict passed by convention; this gives that shared state an
owner with a real API instead.
"""
from __future__ import annotations
from typing import Dict, Optional, Tuple

Seats = Tuple[Optional[int], Optional[int]]


class RoomMembership:
    def __init__(self) -> None:
        self._seats: Dict[str, Seats] = {}

    def add(self, room_id: str, white_user_id: Optional[int], black_user_id: Optional[int]) -> None:
        """Record (or overwrite) both seats for room_id."""
        self._seats[room_id] = (white_user_id, black_user_id)

    def get(self, room_id: str) -> Seats:
        """Return (white_user_id, black_user_id) for room_id, or (None, None) if unknown."""
        return self._seats.get(room_id, (None, None))

    def remove(self, room_id: str) -> Seats:
        """Pop and return room_id's seats, or (None, None) if it was never recorded."""
        return self._seats.pop(room_id, (None, None))
