import pytest

from network.broadcast import WebsocketBroadcaster
from network.session import ClientSession


class _FakeWebSocket:
    def __init__(self, raises: bool = False):
        self.sent = []
        self._raises = raises

    async def send(self, raw: str) -> None:
        if self._raises:
            from websockets.exceptions import ConnectionClosed
            raise ConnectionClosed(None, None)
        self.sent.append(raw)


def _session(ws) -> ClientSession:
    return ClientSession.new(websocket=ws)


@pytest.mark.asyncio
async def test_broadcast_sends_to_every_session():
    ws_a, ws_b = _FakeWebSocket(), _FakeWebSocket()
    broadcaster = WebsocketBroadcaster()

    await broadcaster.broadcast([_session(ws_a), _session(ws_b)], 'hello')

    assert ws_a.sent == ['hello']
    assert ws_b.sent == ['hello']


@pytest.mark.asyncio
async def test_broadcast_ignores_empty_session_list():
    broadcaster = WebsocketBroadcaster()
    await broadcaster.broadcast([], 'hello')  # must not raise


@pytest.mark.asyncio
async def test_broadcast_swallows_connection_closed_for_one_session_and_still_sends_to_others():
    broken, healthy = _FakeWebSocket(raises=True), _FakeWebSocket()
    broadcaster = WebsocketBroadcaster()

    await broadcaster.broadcast([_session(broken), _session(healthy)], 'hello')

    assert healthy.sent == ['hello']
