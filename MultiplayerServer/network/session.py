from __future__ import annotations
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Role(Enum):
    """
    A connected client's role in the match.

    Only WHITE/BLACK exist through Phase 1-4. VIEWER is added in Phase 5
    (game/rooms.py) — no phase before that may reference a spectator concept.

    can_move is written as "is this one of the playing colors" rather than
    "is this not VIEWER" specifically so game/commands.py's viewer gate can
    be written once, now, and never touched again once Phase 5 adds VIEWER —
    it doesn't need to name a role that doesn't exist yet.
    """
    WHITE = 'white'
    BLACK = 'black'

    @property
    def can_move(self) -> bool:
        return self in (Role.WHITE, Role.BLACK)


@dataclass
class ClientSession:
    """
    One connected client.

    role starts unset (None) at connect time (Phase 3 on): a session is
    only ever a WHITE/BLACK player once the matchmaker pairs it with an
    opponent (matchmaking/matchmaker_loop.py), and goes back to None once
    that match ends. No client message ever sets or spoofs it directly —
    it's server logic alone, same anchor fact as before, just assigned
    later than connection time now instead of at it.

    user_id/username start unset and are filled in by a successful
    'register'/'login' (network/dispatch.py) — gates in front of queueing
    (queue_join requires user_id is not None), not a replacement for it.
    """
    session_id: str
    websocket: object
    role: Optional[Role] = None
    user_id: Optional[int] = None
    username: Optional[str] = None

    @staticmethod
    def new(websocket: object, role: Optional[Role] = None) -> 'ClientSession':
        return ClientSession(session_id=str(uuid.uuid4()), websocket=websocket, role=role)
