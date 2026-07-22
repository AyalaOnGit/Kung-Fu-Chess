"""
Entrypoint for networked play: chains home_shell.py's shell login ->
lobby_window.py's Play/Room lobby -> main.py's networked game screen.

UI/main.py remains runnable standalone (`python main.py`) for local
two-player hotseat play; this script is the "online" path.

Usage:
    python play_online.py [ws://host:port]
"""
from __future__ import annotations
import importlib.util
import sys
import pathlib

ui_dir = pathlib.Path(__file__).parent
if str(ui_dir) not in sys.path:
    sys.path.insert(0, str(ui_dir))

import server_bridge  # noqa: F401  -- must run before any kungfu_chess import

from home_shell import DEFAULT_URI, connect_and_login
from lobby_window import run_lobby
from observability.logging_conf import log_event


def _load_game_main():
    """
    Load UI/main.py by explicit file path rather than `import main`: by the
    time this runs, server_bridge has put ChessEngine/ ahead of UI/ on
    sys.path (so kungfu_chess resolves), which means a bare `import main`
    would be ambiguous with any top-level main.py ChessEngine/ ever grows --
    they'd share the same top-level module name.
    """
    spec = importlib.util.spec_from_file_location('ui_game_main', ui_dir / 'main.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main(uri: str = DEFAULT_URI) -> None:
    ws_client, username, resume = connect_and_login(uri)

    white_username = white_elo = black_username = black_elo = None
    if resume is not None:
        # A reconnect within the grace period: the server already rebound
        # us into our in-progress room -- skip the lobby entirely. The
        # state_sync reply carries the same rating fields as match_found/
        # room_joined (opponent fields are None if they're not connected).
        role, room_id, state = resume.data['role'], resume.data['room_id'], resume.data['state']
        white_username, white_elo = resume.data.get('white_username'), resume.data.get('white_elo')
        black_username, black_elo = resume.data.get('black_username'), resume.data.get('black_elo')
    else:
        result = run_lobby(ws_client, username)
        if result is None:
            print('Left the lobby without starting a game.')
            ws_client.close()
            return
        role, room_id, state = result.role, result.room_id, result.state
        white_username, white_elo = result.white_username, result.white_elo
        black_username, black_elo = result.black_username, result.black_elo

    print(f'Entering room {room_id} as {role}.')
    log_event('entering room %s as %s', room_id, role)

    game_main = _load_game_main()
    board_mapper = game_main._build_mapper(game_main.Board(width=8, height=8))

    try:
        game_main.run_network_game(ws_client, board_mapper, role, room_id, state,
                                    white_username=white_username, white_elo=white_elo,
                                    black_username=black_username, black_elo=black_elo)
    finally:
        ws_client.close()


if __name__ == '__main__':
    uri = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URI
    try:
        main(uri)
    except KeyboardInterrupt:
        print('\nInterrupted.')
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
