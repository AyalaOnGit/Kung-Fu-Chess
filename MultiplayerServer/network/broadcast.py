"""
Broadcaster: sends a raw wire message to a set of sessions.

game/rooms.py depends on this Protocol rather than importing
network.server.SessionManager's concrete type and reaching into
session.websocket.send(...) directly -- game/ shouldn't need to know how
a message physically reaches a client, only that it can hand one to
something that broadcasts it. WebsocketBroadcaster is the concrete,
production implementation network/ provides.
"""
from __future__ import annotations
from typing import Iterable, Protocol

from websockets.exceptions import ConnectionClosed

from network.session import ClientSession


class Broadcaster(Protocol):
    async def broadcast(self, sessions: Iterable[ClientSession], raw: str) -> None:
        """Send raw to every session in sessions, ignoring ones that already disconnected."""
        ...


class WebsocketBroadcaster:
    """Sends over each session's live websocket connection."""

    async def broadcast(self, sessions: Iterable[ClientSession], raw: str) -> None:
        for session in sessions:
            try:
                await session.websocket.send(raw)
            except ConnectionClosed:
                pass  # the session's own connection handler will clean it up
