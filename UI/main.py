"""
Kung-Fu Chess UI -- entrypoints.

run_local_game(): the original local two-player hotseat mode (unchanged
behavior) -- both colors are played on the same board/window.

run_network_game(): networked mode, driven by a NetworkGameFacade instead
of a local GameEngine/GameFacade. Used by play_online.py after
home_shell.py's shell login and lobby_window.py's Play/Room lobby produce a
WsClient + role + room_id + initial board state.

Both share _run_game_loop(): the render/tick loop, HUD, sound, and UI
component wiring are identical regardless of which facade is driving the
board -- only facade/board construction differs.
"""
from __future__ import annotations
import sys
import pathlib
import time
from typing import Optional

# Add UI directory to path
ui_dir = pathlib.Path(__file__).parent
if str(ui_dir) not in sys.path:
    sys.path.insert(0, str(ui_dir))

# MUST import server_bridge first, before any server imports
import server_bridge  # noqa: F401

from ui_config import (WINDOW_TITLE, BOARD_IMAGE_PATH, PIECES_PATH, FPS_TARGET,
                       PLAYER_WHITE, PLAYER_BLACK,
                       BOARD_OFFSET_X, BOARD_OFFSET_Y,
                       BOARD_COL_BOUNDARIES, BOARD_ROW_BOUNDARIES)
from graphics.window import Window
from graphics.sprite_loader import SpriteLoader
from graphics.renderer import BoardRenderer
from graphics.hud_renderer import HudRenderer
from animation.animation_clock import AnimationClock
from user_input.mouse_controller import MouseController
from state.game_facade import GameFacade
from ui_components.moves_log_panel import MovesLogPanel
from ui_components.score_panel import ScorePanel
from ui_components.game_over_banner import GameOverBanner
from ui_components.halt_flash import HaltFlashTracker
from ui_components.network_status_panel import NetworkStatusPanel
from audio.sound_manager import SoundManager
from kungfu_chess.model.piece import Color
from kungfu_chess.model.board import Board

from kungfu_chess.factory import build_engine
from kungfu_chess.io.board_factory import standard_board
from kungfu_chess.input.board_mapper import BoardMapper


def _build_mapper(board: Board) -> BoardMapper:
    return BoardMapper(board.width, board.height,
                        offset_x=BOARD_OFFSET_X, offset_y=BOARD_OFFSET_Y,
                        col_boundaries=BOARD_COL_BOUNDARIES,
                        row_boundaries=BOARD_ROW_BOUNDARIES)


def run_local_game() -> None:
    """Local two-player hotseat mode: both colors on one board/window."""
    board = standard_board()
    engine = build_engine(board)
    mapper = _build_mapper(board)
    facade = GameFacade(engine, mapper)

    # Local hotseat mode has no single "local player" color, so GameOver
    # plays a neutral tone rather than a win/lose one (see SoundManager).
    sound_manager = SoundManager(my_color=None)

    _run_game_loop(facade, board, mapper, sound_manager)


def run_network_game(ws_client, mapper: BoardMapper, my_role: str, room_id: str, initial_state: dict,
                      white_username: Optional[str] = None, white_elo: Optional[int] = None,
                      black_username: Optional[str] = None, black_elo: Optional[int] = None) -> None:
    """Networked mode: board driven entirely by MultiplayerServer, via
    NetworkGameFacade. Imported lazily to keep the local-only path free of
    any networking import (websockets isn't needed to play hotseat).

    white_username/white_elo/black_username/black_elo come from either
    lobby_window.py's LobbyResult (match_found/room_created/room_joined) or,
    on a reconnect, straight from the login's state_sync envelope (see
    play_online.py) -- purely for HUD display, so all four are optional and
    None just falls back to the generic PLAYER_WHITE/BLACK labels with no
    rating shown."""
    from network.network_game_facade import NetworkGameFacade

    facade = NetworkGameFacade(ws_client, mapper, initial_state, my_role)
    sound_manager = SoundManager(my_color=facade.my_color)
    network_status_panel = NetworkStatusPanel()
    facade.subscribe(network_status_panel.on_event)

    _run_game_loop(facade, facade.board, mapper, sound_manager,
                    room_id=room_id, my_role=my_role, network_status_panel=network_status_panel,
                    white_username=white_username, white_elo=white_elo,
                    black_username=black_username, black_elo=black_elo)


def _run_game_loop(facade, board: Board, mapper: BoardMapper, sound_manager: SoundManager,
                    room_id: Optional[str] = None, my_role: Optional[str] = None,
                    network_status_panel: Optional[NetworkStatusPanel] = None,
                    white_username: Optional[str] = None, white_elo: Optional[int] = None,
                    black_username: Optional[str] = None, black_elo: Optional[int] = None) -> None:
    """Shared render/tick loop for both local and networked play. `facade`
    is a GameFacade or NetworkGameFacade -- both expose the same interface
    (subscribe/request_click/request_jump/tick/get_selected_pos/
    get_cooldown_ratio/get_pending_motion), so nothing below needs to know
    which one it has."""
    pieces_path = ui_dir / PIECES_PATH
    board_img_path = ui_dir / BOARD_IMAGE_PATH
    sprite_loader = SpriteLoader(pieces_path)

    renderer = BoardRenderer(board, sprite_loader, str(board_img_path), facade, mapper)
    hud_renderer = HudRenderer(800, 800,
                                player_white=white_username or PLAYER_WHITE,
                                player_black=black_username or PLAYER_BLACK,
                                white_elo=white_elo, black_elo=black_elo)
    hud_renderer.set_pieces_dir(pieces_path)
    hud_renderer.set_room_id(room_id)
    hud_renderer.set_my_role(my_role)

    mouse_controller = MouseController(facade.request_click, facade.request_jump)

    # Networked play opens one window per player -- on one desktop (e.g.
    # testing solo with two terminals) two windows with an identical title
    # and no visible distinction are easy to mix up and click the wrong
    # one. The role suffix (and the HUD's "You are: ..." line above) make
    # each window identifiable at a glance.
    window_title = f'{WINDOW_TITLE} -- {my_role.upper()}' if my_role else WINDOW_TITLE
    window = Window(window_title, 800 + 300, 800)
    window.set_mouse_callback(mouse_controller.on_mouse_event)
    print(f'Window: "{window_title}". Zoom: press +/- with the window focused (no drag-resize -- '
          f'that broke click-to-cell mapping on this OpenCV build, see graphics/window.py).')

    clock = AnimationClock()

    def on_event(event):
        print(f"Event: {type(event).__name__}: {event}")

    moves_log_panel = MovesLogPanel()
    score_panel = ScorePanel()
    game_over_banner = GameOverBanner(white_name=white_username or PLAYER_WHITE,
                                       black_name=black_username or PLAYER_BLACK)
    halt_flash_tracker = HaltFlashTracker()
    facade.subscribe(on_event)
    facade.subscribe(moves_log_panel.on_event)
    facade.subscribe(score_panel.on_event)
    facade.subscribe(game_over_banner.on_event)
    facade.subscribe(halt_flash_tracker.on_event)
    facade.subscribe(sound_manager.on_event)
    sound_manager.play_start()

    target_frame_ms = 1000.0 / FPS_TARGET
    frame_count = 0

    while window.is_open():
        frame_start = time.perf_counter()

        dt_ms = clock.tick()
        if dt_ms > 200:  # Cap max dt to prevent jumps
            dt_ms = 200

        try:
            facade.tick(dt_ms)
        except Exception as e:
            print(f"Error in facade.tick: {e}")
            import traceback
            traceback.print_exc()

        halt_flash_tracker.tick(dt_ms)
        if network_status_panel is not None:
            network_status_panel.tick(dt_ms)

        try:
            renderer.set_selection(facade.get_selected_pos())
            renderer.set_halted_piece(
                halt_flash_tracker.get_flashing_piece_id() if halt_flash_tracker.is_flashing() else None
            )
            board_frame = renderer.render(dt_ms)
            hud_renderer.set_moves(moves_log_panel.get_moves())
            hud_renderer.update_score(
                white_score=score_panel.get_score(Color.WHITE),
                black_score=score_panel.get_score(Color.BLACK),
                white_captured=score_panel.get_captured(Color.WHITE),
                black_captured=score_panel.get_captured(Color.BLACK),
            )
            hud_renderer.set_game_over(game_over_banner.get_info())
            if network_status_panel is not None:
                hud_renderer.set_network_status(network_status_panel.get_status_message())
            full_frame = hud_renderer.render(board_frame)
        except Exception as e:
            print(f"Error in rendering: {e}")
            import traceback
            traceback.print_exc()
            break

        fps = 1000.0 / dt_ms if dt_ms > 0 else 0
        window.display_frame(full_frame, fps=fps)

        elapsed_ms = (time.perf_counter() - frame_start) * 1000.0
        remaining_ms = target_frame_ms - elapsed_ms
        if remaining_ms > 0:
            time.sleep(remaining_ms / 1000.0)

        frame_count += 1
        if frame_count % 60 == 0:
            print(f"Frame {frame_count}, FPS: {fps:.1f}")

    window.close()
    print("Game ended")


if __name__ == '__main__':
    try:
        run_local_game()
    except KeyboardInterrupt:
        print("\nGame interrupted")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
