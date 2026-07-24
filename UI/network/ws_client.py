"""
WsClient: background-thread WebSocket connection to MultiplayerServer.

The UI's render loop (UI/main.py) is fully synchronous -- no asyncio
anywhere in UI/ before this file. Rather than rewriting that loop around
asyncio, WsClient runs its own asyncio event loop on a dedicated background
thread and exposes a synchronous, thread-safe interface: send() hands a
command to the network thread, poll_events() drains everything the network
thread has received since the last call. The render loop is expected to
call poll_events() once per frame, exactly like it already calls
facade.tick(dt_ms) once per frame.
"""
from __future__ import annotations
import asyncio
import queue
import threading
from typing import List, Optional

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from network.protocol import Envelope, MalformedEnvelopeError, decode, encode
from observability.logging_conf import log_command, log_event


class WsClient:
    """Owns one persistent WebSocket connection on a background thread."""

    def __init__(self, uri: str):
        self._uri = uri
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._websocket = None
        self._thread: Optional[threading.Thread] = None
        self._incoming: "queue.Queue[Envelope]" = queue.Queue()
        self._connected = threading.Event()
        self._closed = threading.Event()
        self._connect_error: Optional[Exception] = None

    # --- lifecycle ---

    def connect(self, timeout: float = 10.0, run_loop=None) -> None:
        """Start the background thread and block until connected (or raise).

        :param run_loop: injectable stand-in for self._run_loop, for tests.
        """
        self._thread = threading.Thread(target=run_loop or self._run_loop, daemon=True)
        self._thread.start()
        if not self._connected.wait(timeout):
            raise ConnectionError(f'timed out connecting to {self._uri}')
        if self._connect_error is not None:
            raise self._connect_error

    def close(self) -> None:
        if self._loop is None or self._closed.is_set():
            return
        self._closed.set()
        try:
            asyncio.run_coroutine_threadsafe(self._close_websocket(), self._loop)
        except RuntimeError:
            pass  # loop already stopped
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set() and not self._closed.is_set()

    # --- commands / events ---

    def send(self, envelope_type: str, data: Optional[dict] = None) -> None:
        """Thread-safe: enqueue a command to be sent on the network thread."""
        if self._loop is None:
            raise RuntimeError('WsClient.send() called before connect()')
        envelope = Envelope(type=envelope_type, data=data or {})
        log_command('sent', envelope_type, envelope.data)
        asyncio.run_coroutine_threadsafe(self._send(envelope), self._loop)

    def poll_events(self) -> List[Envelope]:
        """Non-blocking: drain and return everything received since the last call."""
        events = []
        while True:
            try:
                events.append(self._incoming.get_nowait())
            except queue.Empty:
                break
        return events

    # --- background thread body ---

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        finally:
            self._loop.close()

    async def _main(self) -> None:
        try:
            self._websocket = await connect(self._uri)
        except Exception as e:
            self._connect_error = e
            self._connected.set()
            return

        self._connected.set()
        log_event('connected to %s', self._uri)
        try:
            async for raw in self._websocket:
                try:
                    envelope = decode(raw)
                except MalformedEnvelopeError:
                    continue
                log_command('recv', envelope.type, envelope.data)
                self._incoming.put(envelope)
        except ConnectionClosed:
            pass
        finally:
            log_event('disconnected from %s', self._uri)
            self._closed.set()

    async def _send(self, envelope: Envelope) -> None:
        if self._websocket is None:
            return
        try:
            await self._websocket.send(encode(envelope))
        except ConnectionClosed:
            pass

    async def _close_websocket(self) -> None:
        if self._websocket is not None:
            await self._websocket.close()
