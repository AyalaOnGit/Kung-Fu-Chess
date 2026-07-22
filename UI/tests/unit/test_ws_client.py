"""
Unit tests for UI/network/ws_client.py, exercised against a real local
WebSocket server (no mocks) so the background-thread/asyncio-loop plumbing
is actually verified end-to-end.
"""
import asyncio
import json
import sys
import pathlib
import threading
import time

import pytest

ui_dir = pathlib.Path(__file__).parent.parent.parent
if str(ui_dir) not in sys.path:
    sys.path.insert(0, str(ui_dir))

import path_bootstrap  # noqa: F401

from websockets.asyncio.server import serve

from network.ws_client import WsClient


class _EchoServer:
    """A tiny background WebSocket server: echoes 'ping' as 'pong', and
    exposes received messages for assertions."""

    def __init__(self):
        self.received = []
        self._loop = None
        self._server = None
        self._thread = None
        self._ready = threading.Event()
        self.port = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        assert self._ready.wait(5.0), 'echo server failed to start'

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())

    async def _serve(self):
        self._server = await serve(self._handler, 'localhost', 0)
        self.port = self._server.sockets[0].getsockname()[1]
        self._ready.set()
        await self._server.wait_closed()

    async def _handler(self, websocket):
        async for raw in websocket:
            self.received.append(raw)
            envelope = json.loads(raw)
            if envelope['type'] == 'ping':
                await websocket.send(json.dumps({'type': 'pong', 'data': {}}))

    def stop(self):
        if self._loop is not None and self._server is not None:
            self._loop.call_soon_threadsafe(self._server.close)
        if self._thread is not None:
            self._thread.join(timeout=5.0)


@pytest.fixture
def echo_server():
    server = _EchoServer()
    server.start()
    yield server
    server.stop()


def test_connect_send_and_receive_roundtrip(echo_server):
    client = WsClient(f'ws://localhost:{echo_server.port}')
    client.connect(timeout=5.0)
    assert client.is_connected

    client.send('ping', {})

    deadline = time.monotonic() + 5.0
    events = []
    while time.monotonic() < deadline and not events:
        events = client.poll_events()
        if not events:
            time.sleep(0.05)

    assert len(events) == 1
    assert events[0].type == 'pong'
    assert json.loads(echo_server.received[0]) == {'type': 'ping', 'data': {}}

    client.close()


def test_poll_events_is_non_blocking_and_empty_when_nothing_arrived(echo_server):
    client = WsClient(f'ws://localhost:{echo_server.port}')
    client.connect(timeout=5.0)

    assert client.poll_events() == []

    client.close()


def test_connect_raises_on_unreachable_server():
    client = WsClient('ws://localhost:1')  # port 1: nothing listens there

    with pytest.raises(Exception):
        client.connect(timeout=5.0)


def test_close_marks_client_as_disconnected(echo_server):
    client = WsClient(f'ws://localhost:{echo_server.port}')
    client.connect(timeout=5.0)
    assert client.is_connected

    client.close()

    assert not client.is_connected


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
