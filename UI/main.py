"""
Kung-Fu Chess UI — Main entrypoint.

Builds the game facade, renderer, window, and runs the game loop.
"""
from __future__ import annotations
import sys
import pathlib
import time

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
from kungfu_chess.model.piece import Color

from kungfu_chess.factory import build_engine
from kungfu_chess.io.board_parser import parse_board
from kungfu_chess.input.board_mapper import BoardMapper


def main():
    """Main entry point."""

    # Initialize game server
    # Create a standard 8x8 chess board with starting position
    engine, board = build_game_engine_and_board()

    mapper = BoardMapper(board.width, board.height,
                         offset_x=BOARD_OFFSET_X, offset_y=BOARD_OFFSET_Y,
                         col_boundaries=BOARD_COL_BOUNDARIES,
                         row_boundaries=BOARD_ROW_BOUNDARIES)

    # Initialize UI components
    pieces_path = ui_dir / PIECES_PATH
    board_img_path = ui_dir / BOARD_IMAGE_PATH

    sprite_loader = SpriteLoader(pieces_path)

    # Game facade handles user clicks and motion prediction
    facade = GameFacade(engine, mapper)

    renderer = BoardRenderer(board, sprite_loader, str(board_img_path), facade, mapper)
    hud_renderer = HudRenderer(800, 800, player_white=PLAYER_WHITE, player_black=PLAYER_BLACK)
    hud_renderer.set_pieces_dir(pieces_path)

    # Mouse input — double-click triggers jump, single click triggers move
    mouse_controller = MouseController(facade.request_click, facade.request_jump)

    # Window
    window = Window(WINDOW_TITLE, 800 + 300, 800)
    window.set_mouse_callback(mouse_controller.on_mouse_event)

    # Animation clock
    clock = AnimationClock()

    # Subscribe to facade events
    def on_event(event):
        print(f"Event: {type(event).__name__}: {event}")

    moves_log_panel = MovesLogPanel()
    score_panel = ScorePanel()
    game_over_banner = GameOverBanner()
    halt_flash_tracker = HaltFlashTracker()
    facade.subscribe(on_event)
    facade.subscribe(moves_log_panel.on_event)
    facade.subscribe(score_panel.on_event)
    facade.subscribe(game_over_banner.on_event)
    facade.subscribe(halt_flash_tracker.on_event)

    target_frame_ms = 1000.0 / FPS_TARGET

    # Main loop
    frame_count = 0

    while window.is_open():
        frame_start = time.perf_counter()

        # Cap frame rate
        dt_ms = clock.tick()
        if dt_ms > 200:  # Cap max dt to prevent jumps
            dt_ms = 200

        # Facade tick (handles motion, events)
        try:
            facade.tick(dt_ms)
        except Exception as e:
            print(f"Error in facade.tick: {e}")
            import traceback
            traceback.print_exc()

        halt_flash_tracker.tick(dt_ms)

        # Render
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
            hud_renderer.set_game_over(
                game_over_banner.get_message() if game_over_banner.should_display() else None
            )
            full_frame = hud_renderer.render(board_frame)
        except Exception as e:
            print(f"Error in rendering: {e}")
            import traceback
            traceback.print_exc()
            break

        # Display
        fps = 1000.0 / dt_ms if dt_ms > 0 else 0
        window.display_frame(full_frame, fps=fps)

        # Cap to FPS_TARGET by sleeping out the remainder of the frame budget
        elapsed_ms = (time.perf_counter() - frame_start) * 1000.0
        remaining_ms = target_frame_ms - elapsed_ms
        if remaining_ms > 0:
            time.sleep(remaining_ms / 1000.0)

        frame_count += 1
        if frame_count % 60 == 0:
            print(f"Frame {frame_count}, FPS: {fps:.1f}")

    window.close()
    print("Game ended")




def build_game_engine_and_board():
    """
    Build a standard chess board with starting position.

    Returns (engine, board)
    """
    # Standard chess starting position
    starting_position = [
        "bR bN bB bQ bK bB bN bR",
        "bP bP bP bP bP bP bP bP",
        ".  .  .  .  .  .  .  .  ",
        ".  .  .  .  .  .  .  .  ",
        ".  .  .  .  .  .  .  .  ",
        ".  .  .  .  .  .  .  .  ",
        "wP wP wP wP wP wP wP wP",
        "wR wN wB wQ wK wB wN wR",
    ]

    board = parse_board(starting_position)
    engine = build_engine(board)
    return engine, board


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nGame interrupted")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
