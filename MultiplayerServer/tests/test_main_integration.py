"""
Integration regression test for a real bug found in production use: when a
game ends by king capture, the terminal event batch (move_accepted/
piece_captured/piece_arrived/game_over) was published onto the Bus
correctly but never reached either client's websocket.

Root cause (main.py's on_game_over): it synchronously cleared
session.room_id for every session in the room right after the winning
move's events were published. game/rooms.py's broadcaster is a separate
queued Bus subscriber task that filters "who's in this room" by reading
session.room_id *at delivery time*, not at publish time -- clearing it
inline reliably beat that subscriber task to the punch, so the entire
final batch was silently dropped for everyone. This can only be exercised
with genuine asyncio task scheduling and real (or real-shaped) async
sends, not the room_manager/dispatch unit tests elsewhere in this suite
(those admit sessions with websocket=None), so this test runs an actual
MultiplayerServer over a real localhost websocket, seeded with a
custom board where one player's king starts adjacent to the other's --
one move away from ending the game -- so the terminal broadcast is
exercised without playing out a full legal game.
"""
from __future__ import annotations
import asyncio
import json

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

# Must import this package's own main.py *before* anything that pulls in
# game.engine_path (below): that module inserts Server/ onto sys.path so
# `import kungfu_chess` resolves, which as a side effect makes a bare
# `import main` resolve to Server/main.py instead of this one -- same
# top-level module name, and Server/ would now sort first.
import main as server_main

import game.engine_path  # noqa: F401  (must run before any kungfu_chess import)
import game.engine_factory
from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Color, Kind, Piece
from kungfu_chess.model.position import Position

HOST = '127.0.0.1'
PORT = 8799


def _adjacent_kings_board() -> Board:
    board = Board(width=8, height=8)
    board.add_piece(Piece(id=1, color=Color.WHITE, kind=Kind.KING, cell=Position(4, 4)))
    board.add_piece(Piece(id=2, color=Color.BLACK, kind=Kind.KING, cell=Position(4, 5)))
    return board


async def _recv_json(websocket) -> dict:
    return json.loads(await websocket.recv())


async def _send(websocket, msg_type: str, data: dict) -> None:
    await websocket.send(json.dumps({'type': msg_type, 'data': data}))


async def _wait_for(websocket, *types: str, timeout: float = 5.0) -> dict:
    async def _loop():
        while True:
            envelope = await _recv_json(websocket)
            if envelope['type'] in types:
                return envelope
    return await asyncio.wait_for(_loop(), timeout=timeout)


async def _wait_for_all(websocket, *types: str, timeout: float = 5.0) -> dict:
    """Like _wait_for, but collects one envelope per type in `types`,
    keyed by type -- for envelopes whose relative arrival order isn't
    guaranteed (e.g. game_over's room broadcast vs rating_update's direct
    send both follow the same king-capture, from different code paths)."""
    remaining = set(types)
    found = {}

    async def _loop():
        while remaining:
            envelope = await _recv_json(websocket)
            if envelope['type'] in remaining:
                found[envelope['type']] = envelope
                remaining.discard(envelope['type'])
        return found
    return await asyncio.wait_for(_loop(), timeout=timeout)


@pytest_asyncio.fixture
async def running_server(monkeypatch):
    """A real MultiplayerServer instance, seeded so a fresh room's two
    kings start adjacent (one move apart from a capture)."""
    # game/engine_factory.py did `from kungfu_chess.io.board_factory import
    # standard_board`, binding its own local name -- patch that reference
    # (where create_room's fresh-room path actually calls it), not the
    # kungfu_chess-side original.
    monkeypatch.setattr(game.engine_factory, 'standard_board', _adjacent_kings_board)

    server_task = asyncio.create_task(server_main.run(host=HOST, port=PORT, db_path=':memory:'))
    await asyncio.sleep(0.2)  # let the server actually start listening
    try:
        yield f'ws://{HOST}:{PORT}'
    finally:
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_king_capture_broadcasts_game_over_to_both_players(running_server):
    uri = running_server

    async with connect(uri) as white_ws, connect(uri) as black_ws:
        await _recv_json(white_ws)  # 'connected' greeting
        await _recv_json(black_ws)

        await _send(white_ws, 'register', {'username': 'itg_white', 'password': 'hunter2'})
        await _wait_for(white_ws, 'registered')
        await _send(black_ws, 'register', {'username': 'itg_black', 'password': 'hunter2'})
        await _wait_for(black_ws, 'registered')

        await _send(white_ws, 'create_room', {})
        room_created = await _wait_for(white_ws, 'room_created')
        room_id = room_created['data']['room_id']

        await _send(black_ws, 'join_room', {'room_id': room_id})
        await _wait_for(black_ws, 'room_joined')

        # White's king captures black's king one square away.
        await _send(white_ws, 'move', {'src': [4, 4], 'dest': [4, 5]})
        accepted = await _wait_for(white_ws, 'accepted', 'error')
        assert accepted['type'] == 'accepted'

        # game_over (the room's own broadcast) and rating_update (a separate
        # direct send once record_match_result finishes its DB round-trip)
        # both follow the same king-capture, but from different code paths
        # with no ordering guarantee between them -- collect both rather
        # than assuming which arrives first.
        white_results = await _wait_for_all(white_ws, 'game_over', 'rating_update', timeout=5.0)
        black_results = await _wait_for_all(black_ws, 'game_over', 'rating_update', timeout=5.0)

        assert white_results['game_over']['data'] == {'winner': 'w', 'loser': 'b'}
        assert black_results['game_over']['data'] == {'winner': 'w', 'loser': 'b'}

        # Both fresh accounts start at 1200, so a win/loss between them
        # moves by the same fixed K-factor amount.
        expected_rating_data = {
            'white_elo_before': 1200, 'white_elo_after': 1216,
            'black_elo_before': 1200, 'black_elo_after': 1184,
        }
        assert white_results['rating_update']['data'] == expected_rating_data
        assert black_results['rating_update']['data'] == expected_rating_data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
