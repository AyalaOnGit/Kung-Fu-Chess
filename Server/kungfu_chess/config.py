from __future__ import annotations

# --- Board / pixel geometry ---
CELL_SIZE_PX    = 100   # pixels per board cell
PIECE_SPEED_PPS = 100   # pixels per second => 1 cell = 1000 ms

# --- Timing ---
JUMP_DURATION_MS = 3000  # ms a piece stays airborne during a jump
COOLDOWN_MS     = 1500  # ms a piece must wait after arriving before it can move again

# --- Move result reasons ---
REASON_OK                  = 'ok'
REASON_GAME_OVER           = 'game_over'
REASON_MOTION_IN_PROGRESS  = 'motion_in_progress'
REASON_OUTSIDE_BOARD       = 'outside_board'
REASON_EMPTY_SOURCE        = 'empty_source'
REASON_FRIENDLY_DEST       = 'friendly_destination'
REASON_ILLEGAL_MOVE        = 'illegal_piece_move'
