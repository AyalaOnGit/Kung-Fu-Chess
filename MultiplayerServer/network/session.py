from __future__ import annotations
import uuid
from dataclasses import dataclass
from typing import Optional

from core.protocol import Role


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
