"""
Ensures UI/ is on sys.path and ChessEngine/kungfu_chess is importable
regardless of the cwd pytest was invoked from -- so `pytest tests` run
from inside UI/ and `pytest UI/tests` run from the repo root resolve
every UI-local absolute import (graphics.*, state.*, ...) the same way.
Runs once per session, before any test module's own imports.
"""
import pathlib
import sys

_ui_dir = pathlib.Path(__file__).parent.parent
if str(_ui_dir) not in sys.path:
    sys.path.insert(0, str(_ui_dir))

import path_bootstrap  # noqa: F401  -- must run before any kungfu_chess import
