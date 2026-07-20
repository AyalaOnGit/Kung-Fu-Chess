"""All tunables in one place — no magic numbers scattered through the codebase."""
from __future__ import annotations

TICK_INTERVAL_MS = 50  # 20 ticks/sec: how often a Room advances engine time and diffs events.
DB_PATH = 'kungfu_chess.db'  # relative to the process's working directory
RECONNECT_GRACE_SECONDS = 25.0  # how long a disconnected match participant can reconnect before auto-resigning
