import asyncio
import json

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from network.server import SessionManager, build_handler


@pytest_asyncio.fixture
async def running_server():
    session_manager = SessionManager()
    handler = build_handler(session_manager)
    async with serve(handler, 'localhost', 0) as server:
        port = server.sockets[0].getsockname()[1]
        yield f'ws://localhost:{port}', session_manager


@pytest.mark.asyncio
async def test_connecting_gets_a_connected_ack_with_no_role_yet(running_server):
    uri, _ = running_server
    async with connect(uri) as client:
        msg = json.loads(await client.recv())
        assert msg == {'type': 'connected', 'data': {}}


@pytest.mark.asyncio
async def test_more_than_two_simultaneous_connections_are_all_admitted(running_server):
    # Unlike Phase 1, there's no connection cap — matchmaking (Phase 3 on)
    # needs a queue of more than two people waiting at once.
    uri, session_manager = running_server
    async with connect(uri) as a, connect(uri) as b, connect(uri) as c:
        await a.recv()
        await b.recv()
        await c.recv()
        await asyncio.sleep(0.05)
        assert len(session_manager.sessions) == 3


@pytest.mark.asyncio
async def test_admitted_sessions_start_with_no_role(running_server):
    uri, session_manager = running_server
    async with connect(uri) as client:
        await client.recv()
        await asyncio.sleep(0.05)
        assert session_manager.sessions[0].role is None


@pytest.mark.asyncio
async def test_session_manager_tracks_connected_and_disconnected_sessions(running_server):
    uri, session_manager = running_server
    async with connect(uri) as first:
        await first.recv()
        await asyncio.sleep(0.05)
        assert len(session_manager.sessions) == 1
    await asyncio.sleep(0.05)
    assert len(session_manager.sessions) == 0


@pytest.mark.asyncio
async def test_get_by_user_id_finds_a_session_once_its_user_id_is_set(running_server):
    uri, session_manager = running_server
    async with connect(uri) as client:
        await client.recv()
        await asyncio.sleep(0.05)
        session = session_manager.sessions[0]
        session.user_id = 42

        assert session_manager.get_by_user_id(42) is session
        assert session_manager.get_by_user_id(99) is None


@pytest.mark.asyncio
async def test_on_admit_hook_fires_once_per_admitted_connection():
    session_manager = SessionManager()
    admitted = []
    handler = build_handler(session_manager, on_admit=admitted.append)

    async with serve(handler, 'localhost', 0) as server:
        port = server.sockets[0].getsockname()[1]
        uri = f'ws://localhost:{port}'
        async with connect(uri) as first, connect(uri) as second:
            await first.recv()
            await second.recv()
            await asyncio.sleep(0.05)

    assert len(admitted) == 2
    assert all(s.role is None for s in admitted)


@pytest.mark.asyncio
async def test_on_disconnect_hook_fires_when_the_client_closes_cleanly():
    session_manager = SessionManager()
    disconnected = []

    async def on_disconnect(session):
        disconnected.append(session)

    handler = build_handler(session_manager, on_disconnect=on_disconnect)

    async with serve(handler, 'localhost', 0) as server:
        port = server.sockets[0].getsockname()[1]
        async with connect(f'ws://localhost:{port}') as client:
            await client.recv()  # 'connected'
        await asyncio.sleep(0.05)

    assert len(disconnected) == 1


@pytest.mark.asyncio
async def test_on_disconnect_exception_does_not_prevent_session_removal():
    session_manager = SessionManager()

    async def broken_on_disconnect(_session):
        raise RuntimeError('boom')

    handler = build_handler(session_manager, on_disconnect=broken_on_disconnect)

    async with serve(handler, 'localhost', 0) as server:
        port = server.sockets[0].getsockname()[1]
        async with connect(f'ws://localhost:{port}') as client:
            await client.recv()
        await asyncio.sleep(0.05)

    assert len(session_manager.sessions) == 0


@pytest.mark.asyncio
async def test_on_message_hook_response_is_sent_back_to_the_sender():
    session_manager = SessionManager()

    async def echo(_session, raw: str) -> str:
        return f'echo:{raw}'

    handler = build_handler(session_manager, on_message=echo)

    async with serve(handler, 'localhost', 0) as server:
        port = server.sockets[0].getsockname()[1]
        async with connect(f'ws://localhost:{port}') as client:
            await client.recv()  # 'connected'
            await client.send('hello')
            assert await client.recv() == 'echo:hello'


@pytest.mark.asyncio
async def test_on_message_hook_returning_none_sends_nothing():
    session_manager = SessionManager()

    async def swallow(_session, _raw: str):
        return None

    handler = build_handler(session_manager, on_message=swallow)

    async with serve(handler, 'localhost', 0) as server:
        port = server.sockets[0].getsockname()[1]
        async with connect(f'ws://localhost:{port}') as client:
            await client.recv()  # 'connected'
            await client.send('hello')
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(client.recv(), timeout=0.1)
