"""
UI-only configuration constants.

Does not import from server; these are purely presentation settings.
"""

# Board pixel offset inside board.png (border around the 8x8 grid)
BOARD_OFFSET_X = 2
BOARD_OFFSET_Y = 6
# Exact cell boundary positions (pixels) for each column/row divider
# Measured from board.png (822x828)
BOARD_COL_BOUNDARIES = [2, 104, 206, 309, 412, 515, 618, 720, 821]
BOARD_ROW_BOUNDARIES = [6, 108, 211, 313, 417, 519, 623, 726, 827]

# Window properties
WINDOW_TITLE = "Kung-Fu Chess"
FPS_TARGET = 60

# Window scale (resize with +/-)
SCALE_DEFAULT = 1.0
SCALE_STEP    = 0.1
SCALE_MIN     = 0.5
SCALE_MAX     = 2.0

# Player names
PLAYER_WHITE = "White"
PLAYER_BLACK = "Black"

# Sidebar layout
SIDEBAR_WIDTH_PX = 300
SIDEBAR_BG_COLOR = (40, 40, 40)

# Text rendering
TEXT_COLOR = (200, 200, 200)
TEXT_DARK = (100, 100, 100)

# Piece size relative to cell (0.0–1.0); 0.70 = 70px out of 100px per cell
PIECE_SCALE = 0.70

# Piece animation skin — must match a folder name under assets/
SKIN = "pieces_mine"

# Asset paths (relative to ui/ directory)
BOARD_IMAGE_PATH = "assets/board.png"
PIECES_PATH = f"assets/{SKIN}"
SELECTION_OVERLAY_PATH = "assets/selection_highlight.png"
HALT_FLASH_OVERLAY_PATH = "assets/halt_flash.png"
PANEL_BG_PATH = "assets/panel_background.png"
