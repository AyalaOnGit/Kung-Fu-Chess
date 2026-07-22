from __future__ import annotations

# --- Board / pixel geometry ---
CELL_SIZE_PX    = 100   # pixels per board cell
PIECE_SPEED_PPS = 100   # pixels per second => 1 cell = 1000 ms

# --- Timing ---
# A jump must stay airborne for at least one cell's travel time (1000ms,
# see PIECE_SPEED_PPS above) for it to ever intercept the fastest possible
# incoming attack (an adjacent-cell move) -- RealTimeArbiter._active_jump_at
# requires arrival_time <= landing_time. 1000ms is that floor: fast enough
# to feel snappy (matches a single-cell move's own speed) while still
# covering every legal incoming attack, since 1 cell is the minimum any
# move can take.
JUMP_DURATION_MS = 1000  # ms a piece stays airborne during a jump
COOLDOWN_MS     = 1500  # ms a piece must wait after arriving before it can move again

# --- Move result reasons ---
REASON_OK                  = 'ok'
REASON_GAME_OVER           = 'game_over'
REASON_MOTION_IN_PROGRESS  = 'motion_in_progress'
REASON_OUTSIDE_BOARD       = 'outside_board'
REASON_EMPTY_SOURCE        = 'empty_source'
REASON_FRIENDLY_DEST       = 'friendly_destination'
REASON_ILLEGAL_MOVE        = 'illegal_piece_move'
