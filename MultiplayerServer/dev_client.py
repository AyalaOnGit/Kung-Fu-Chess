"""
Reference CLI client — a protocol consumer like any GUI client would be.
Not imported by anything else in MultiplayerServer/.

Usage:
    python dev_client.py [ws://host:port]

Commands (typed at the prompt, one per line):
    register <username> <password>
    login <username> <password>
    queue
    unqueue
    move <src_row> <src_col> <dest_row> <dest_col>
    jump <row> <col>
    ping
    quit
"""
from __future__ import annotations
import asyncio
import sys
from typing import Optional

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from core.protocol import Envelope, MalformedEnvelopeError, decode, encode

DEFAULT_URI = 'ws://localhost:8765'


def _parse_command(line: str) -> Optional[Envelope]:
    parts = line.split()
    if not parts:
        return None

    cmd = parts[0]
    if cmd == 'move' and len(parts) == 5:
        try:
            sr, sc, dr, dc = (int(p) for p in parts[1:])
        except ValueError:
            print('move needs four integers: move <src_row> <src_col> <dest_row> <dest_col>')
            return None
        return Envelope(type='move', data={'src': [sr, sc], 'dest': [dr, dc]})

    if cmd == 'jump' and len(parts) == 3:
        try:
            row, col = (int(p) for p in parts[1:])
        except ValueError:
            print('jump needs two integers: jump <row> <col>')
            return None
        return Envelope(type='jump', data={'cell': [row, col]})

    if cmd == 'ping' and len(parts) == 1:
        return Envelope(type='ping', data={})

    if cmd == 'register' and len(parts) == 3:
        return Envelope(type='register', data={'username': parts[1], 'password': parts[2]})

    if cmd == 'login' and len(parts) == 3:
        return Envelope(type='login', data={'username': parts[1], 'password': parts[2]})

    if cmd == 'queue' and len(parts) == 1:
        return Envelope(type='queue_join', data={})

    if cmd == 'unqueue' and len(parts) == 1:
        return Envelope(type='queue_cancel', data={})

    print(f'unrecognized command: {line!r}')
    print('usage: register <user> <pw> | login <user> <pw> | queue | unqueue |'
          ' move <sr> <sc> <dr> <dc> | jump <r> <c> | ping | quit')
    return None


async def _receive_loop(websocket) -> None:
    try:
        async for raw in websocket:
            try:
                envelope = decode(raw)
            except MalformedEnvelopeError:
                print(f'<< (unparseable) {raw}')
                continue
            print(f'<< {envelope.type} {envelope.data}')
    except ConnectionClosed:
        print('-- connection closed by server --')


async def _send_loop(websocket) -> None:
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:  # stdin closed (EOF)
            break
        line = line.strip()
        if line == 'quit':
            break
        envelope = _parse_command(line)
        if envelope is not None:
            await websocket.send(encode(envelope))


async def main(uri: str) -> None:
    async with connect(uri) as websocket:
        greeting = decode(await websocket.recv())
        print(f'<< {greeting.type} {greeting.data}')

        receiver = asyncio.create_task(_receive_loop(websocket))
        try:
            await _send_loop(websocket)
        finally:
            receiver.cancel()
            try:
                await receiver
            except asyncio.CancelledError:
                pass


if __name__ == '__main__':
    uri = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URI
    try:
        asyncio.run(main(uri))
    except KeyboardInterrupt:
        pass
