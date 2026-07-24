"""
Unit tests for UI/network/ws_client.py, exercised against a real local
WebSocket server (no mocks) so the background-thread/asyncio-loop plumbing
is actually verified end-to-end.
"""
import asyncio
import json
import threading
import time

import pytest

from websockets.asyncio.server import serve

from network.ws_client import WsClient


class _EchoServer:
    """A tiny background WebSocket server: echoes 'ping' as 'pong', and
    exposes received messages for assertions. send_raw() lets a test push
    arbitrary (including malformed) text to the connected client directly,
    and drop_connection() lets a test end the connection from the server
    side rather than the client side."""

    def __init__(self):
        self.received = []
        self._loop = None
        self._server = None
        self._thread = None
        self._ready = threading.Event()
        self.port = None
        self._websocket = None

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
        self._websocket = websocket
        async for raw in websocket:
            self.received.append(raw)
            envelope = json.loads(raw)
            if envelope['type'] == 'ping':
                await websocket.send(json.dumps({'type': 'pong', 'data': {}}))

    def send_raw(self, raw_text: str, timeout: float = 5.0):
        future = asyncio.run_coroutine_threadsafe(self._websocket.send(raw_text), self._loop)
        future.result(timeout)

    def drop_connection(self, timeout: float = 5.0):
        """Close the connection from the server side (rather than the
        client calling close() itself), so the client's receive loop sees
        the socket go away out from under it."""
        future = asyncio.run_coroutine_threadsafe(self._websocket.close(), self._loop)
        future.result(timeout)

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


def test_connect_raises_connection_error_on_timeout():
    """connect() itself timing out (the background thread never signals
    _connected within the given window) is a different failure mode from
    an immediate connection refusal (already covered above) -- replace the
    thread body with one that never connects to exercise it deterministically
    and quickly rather than relying on a real network-level hang."""
    client = WsClient('ws://this-uri-is-never-actually-used')
    with pytest.raises(ConnectionError, match='timed out'):
        client.connect(timeout=0.05, run_loop=lambda: time.sleep(0.5))


def test_close_before_connect_is_a_no_op():
    client = WsClient('ws://localhost:1')
    client.close()  # must not raise -- self._loop is still None


def test_send_before_connect_raises_runtime_error():
    client = WsClient('ws://localhost:1')
    with pytest.raises(RuntimeError, match='before connect'):
        client.send('ping', {})


def test_malformed_envelope_from_the_server_is_skipped_not_crashed_on(echo_server):
    """decode() raising MalformedEnvelopeError for one message must not
    take down the background thread -- it's skipped, and later, well-formed
    messages on the same connection still arrive normally."""
    client = WsClient(f'ws://localhost:{echo_server.port}')
    client.connect(timeout=5.0)

    echo_server.send_raw('not valid json{{{')
    client.send('ping', {})

    deadline = time.monotonic() + 5.0
    events = []
    while time.monotonic() < deadline and not events:
        events = client.poll_events()
        if not events:
            time.sleep(0.05)

    assert len(events) == 1
    assert events[0].type == 'pong'  # the malformed message was silently dropped

    client.close()


def test_server_dropping_the_connection_leaves_the_client_gracefully_disconnected(echo_server):
    """A server-initiated close (rather than the client calling close()
    itself) must be absorbed quietly -- the client ends up disconnected,
    with no exception escaping the background thread."""
    client = WsClient(f'ws://localhost:{echo_server.port}')
    client.connect(timeout=5.0)
    assert client.is_connected

    # The client side finishing connect() can (rarely) race the server's
    # own _handler coroutine actually being scheduled and recording
    # self._websocket -- give it a brief moment to catch up.
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and echo_server._websocket is None:
        time.sleep(0.01)

    echo_server.drop_connection()

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and client.is_connected:
        time.sleep(0.05)

    assert not client.is_connected


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
