"""
Inserts ChessEngine/ onto sys.path so `import kungfu_chess` resolves.

Mirrors UI/path_bootstrap.py's identical trick for the Img/OpenCV client:
MultiplayerServer/ and UI/ are independent top-level packages that both
depend on ChessEngine/kungfu_chess without it depending on either of them.

Every game/ module that imports kungfu_chess imports this module first
(the insert is idempotent, so doing it in each module is cheap and makes
each module correct on its own regardless of import order).
"""
from __future__ import annotations
import sys
import pathlib

_server_dir = pathlib.Path(__file__).parent.parent.parent / "ChessEngine"
if str(_server_dir) not in sys.path:
    sys.path.insert(0, str(_server_dir))
