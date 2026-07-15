"""
UI-only configuration constants.

Does not import from server; these are purely presentation settings.
"""

# Window properties
WINDOW_TITLE = "Kung-Fu Chess"
FPS_TARGET = 60

# Sidebar layout
SIDEBAR_WIDTH_PX = 300
SIDEBAR_BG_COLOR = (40, 40, 40)

# Text rendering
TEXT_COLOR = (200, 200, 200)
TEXT_DARK = (100, 100, 100)

# Piece size relative to cell (0.0–1.0); 0.75 = 75px out of 100px per cell
PIECE_SCALE = 0.75

# Piece animation skin: "pieces1" or "pieces3"
SKIN = "pieces1"

# Asset paths (relative to ui/ directory)
BOARD_IMAGE_PATH = "assets/board.png"
PIECES_PATH = f"assets/{SKIN}"
SELECTION_OVERLAY_PATH = "assets/selection_highlight.png"
HALT_FLASH_OVERLAY_PATH = "assets/halt_flash.png"
PANEL_BG_PATH = "assets/panel_background.png"
