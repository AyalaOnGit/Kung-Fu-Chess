from __future__ import annotations
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Role(Enum):
    """
    A connected client's role within whatever room it belongs to.

    VIEWER exists from Phase 5 on (game/rooms.py) — no phase before that
    may reference a spectator concept.

    can_move is written as "is this one of the playing colors" rather than
    "is this not VIEWER" — written that way back in Phase 1, before VIEWER
    existed, specifically so game/commands.py's viewer gate would need no
    changes once this enum grew a third member. It didn't.
    """
    WHITE = 'white'
    BLACK = 'black'
    VIEWER = 'viewer'

    @property
    def can_move(self) -> bool:
        return self in (Role.WHITE, Role.BLACK)


@dataclass
class ClientSession:
    """
    One connected client.

    room_id/role start unset (None) at connect time and are only ever set
    together, by server logic alone — never by a client message:
      - matchmaking/matchmaker_loop.py's on_paired sets both when it pairs
        two queued players into a new Room (WHITE/BLACK).
      - network/dispatch.py's create_room/join_room handlers set both when
        a session manually creates or joins a room by id (WHITE, BLACK, or
        VIEWER depending on join order).
    Both go back to None once the room's game ends.

    user_id/username start unset and are filled in by a successful
    'register'/'login' (network/dispatch.py) — gates in front of queueing
    and room-joining (both require user_id is not None), not a replacement
    for them.
    """
    session_id: str
    websocket: object
    role: Optional[Role] = None
    room_id: Optional[str] = None
    user_id: Optional[int] = None
    username: Optional[str] = None

    @staticmethod
    def new(websocket: object, role: Optional[Role] = None) -> 'ClientSession':
        return ClientSession(session_id=str(uuid.uuid4()), websocket=websocket, role=role)
