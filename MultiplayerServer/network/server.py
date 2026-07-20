from __future__ import annotations
import logging
from typing import Awaitable, Callable, Dict, List, Optional

from websockets.asyncio.server import ServerConnection
from websockets.exceptions import ConnectionClosed

from core.protocol import Envelope, encode
from network.session import ClientSession

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Tracks every currently connected client.

    Unlike Phase 1, this no longer assigns a role or caps the connection
    count — matchmaking (Phase 3 on) needs a queue of more than two
    simultaneous connections, so a session starts with role=None and stays
    that way until the matchmaker pairs it with an opponent.
    """

    def __init__(self):
        self._sessions: Dict[str, ClientSession] = {}

    def admit(self, websocket: ServerConnection) -> ClientSession:
        """Register a new, not-yet-matched session for websocket."""
        session = ClientSession.new(websocket)
        self._sessions[session.session_id] = session
        return session

    def remove(self, session: ClientSession) -> None:
        self._sessions.pop(session.session_id, None)

    def get_by_user_id(self, user_id: int) -> Optional[ClientSession]:
        return next((s for s in self._sessions.values() if s.user_id == user_id), None)

    @property
    def sessions(self) -> List[ClientSession]:
        return list(self._sessions.values())


def make_handler(
    session_manager: SessionManager,
    on_admit: Optional[Callable[[ClientSession], None]] = None,
    on_message: Optional[Callable[[ClientSession, str], Awaitable[Optional[str]]]] = None,
    on_disconnect: Optional[Callable[[ClientSession], Awaitable[None]]] = None,
) -> Callable[[ServerConnection], Awaitable[None]]:
    """
    Build the per-connection coroutine websockets.serve runs for each client.

    Stays transport-only: on_admit/on_message/on_disconnect are injected by
    the composition root (main.py, via network/dispatch.py) so this module
    never has to import anything game-related to route a message —
    it just calls the hook and, if it returns text, sends that text back.

    on_disconnect always fires in `finally`, not `except ConnectionClosed`:
    websockets only raises ConnectionClosed for an abnormal close — a
    clean close just ends the `async for` loop normally, and `finally` is
    the one place guaranteed to run either way.
    """

    async def handle_connection(websocket: ServerConnection) -> None:
        session = session_manager.admit(websocket)
        logger.info('session %s connected', session.session_id)
        if on_admit is not None:
            on_admit(session)
        try:
            await websocket.send(encode(Envelope(type='connected', data={})))
            async for raw in websocket:
                if on_message is None:
                    continue
                response = await on_message(session, raw)
                if response is not None:
                    await websocket.send(response)
        except ConnectionClosed:
            pass
        finally:
            if on_disconnect is not None:
                try:
                    await on_disconnect(session)
                except Exception:
                    logger.exception('on_disconnect hook raised for session %s', session.session_id)
            session_manager.remove(session)
            logger.info('session %s disconnected', session.session_id)

    return handle_connection
