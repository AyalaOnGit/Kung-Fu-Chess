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
# Shown instead of PLAYER_BLACK/PLAYER_WHITE while a room's second seat is
# still empty (networked play only -- local hotseat always has both).
WAITING_FOR_OPPONENT = "Waiting for opponent..."

# Sidebar layout
SIDEBAR_WIDTH_PX = 300
SIDEBAR_BG_COLOR = (40, 40, 40)
SIDEBAR_MARGIN_PX = 14

# Text rendering
TEXT_COLOR = (200, 200, 200)

# HUD font scales (cv2 putText font_size units)
HUD_FONT_SCALE_HEADER = 0.65        # player name headers
HUD_FONT_SCALE_SECTION = 0.55       # "Moves" section title
HUD_FONT_SCALE_LABEL = 0.5          # score line
HUD_FONT_SCALE_COLUMN_HEADER = 0.45 # black/white column headers above moves
HUD_FONT_SCALE_MOVE = 0.4           # individual move entries

# Moves log layout
MOVES_LOG_VISIBLE_ROWS = 10
MOVES_LOG_ROW_HEIGHT_PX = 18

# Captured-piece thumbnail size (px)
CAPTURED_THUMB_SIZE_PX = 28

# Piece size relative to cell (0.0–1.0); 0.70 = 70px out of 100px per cell
PIECE_SCALE = 0.70

# Piece animation skin — must match a folder name under assets/
SKIN = "pieces_mine"

# Asset paths (relative to ui/ directory)
BOARD_IMAGE_PATH = "assets/board.png"
PIECES_PATH = f"assets/{SKIN}"

# --- Board overlay colors/sizes (selection, jump ring, cooldown bar) ---
SELECTION_COLOR = (80, 200, 80, 180)
SELECTION_BORDER_COLOR = (100, 255, 100, 255)
SELECTION_BORDER_THICKNESS = 2
SELECTION_FILL_ALPHA = 0.35

JUMP_RING_COLOR = (255, 220, 0, 255)
JUMP_RING_THICKNESS = 3
JUMP_RING_MARGIN_PX = 4

COOLDOWN_BAR_BG_COLOR = (30, 30, 30, 200)
COOLDOWN_BAR_FG_COLOR = (0, 140, 255, 255)
COOLDOWN_BAR_HEIGHT_PX = 6
COOLDOWN_BAR_MARGIN_PX = 4

HALT_FLASH_COLOR = (0, 0, 255, 255)
HALT_FLASH_THICKNESS = 4
HALT_FLASH_DURATION_MS = 200.0

GAME_OVER_OVERLAY_COLOR = (0, 0, 0)
GAME_OVER_OVERLAY_ALPHA = 0.55
GAME_OVER_TEXT_COLOR = (255, 255, 255, 255)
GAME_OVER_TITLE_FONT_SCALE = 1.1
GAME_OVER_DETAIL_FONT_SCALE = 0.65
GAME_OVER_LINE_GAP_PX = 16          # vertical gap between stacked dialog lines
GAME_OVER_PANEL_COLOR = (30, 30, 30, 255)  # 4-tuple: fill_rect_blend runs on a BGRA
                                            # image, and a 3-tuple color leaves the
                                            # rectangle's alpha at 0, blending the
                                            # "opaque" panel toward transparent
GAME_OVER_PANEL_ALPHA = 0.85
GAME_OVER_PANEL_BORDER_COLOR = (110, 110, 110, 255)
GAME_OVER_PANEL_PADDING_X_PX = 36
GAME_OVER_PANEL_PADDING_Y_PX = 26
GAME_OVER_RATING_UP_COLOR = (90, 210, 90, 255)    # BGR: green, ELO gained
GAME_OVER_RATING_DOWN_COLOR = (80, 90, 220, 255)  # BGR: red, ELO lost

# --- Mouse input ---
DOUBLE_CLICK_MS = 300      # ms between two clicks to count as a double-click
DOUBLE_CLICK_RADIUS_PX = 20  # max pixel distance between the two clicks
