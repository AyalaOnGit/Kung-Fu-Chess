"""
Inserts Server/ onto sys.path so `import kungfu_chess` resolves.

Mirrors UI/server_bridge.py's identical trick for the pygame client:
MultiplayerServer/ and UI/ are independent top-level packages that both
depend on Server/kungfu_chess without it depending on either of them.

Every game/ module that imports kungfu_chess imports this module first
(the insert is idempotent, so doing it in each module is cheap and makes
each module correct on its own regardless of import order).
"""
from __future__ import annotations
import sys
import pathlib

_server_dir = pathlib.Path(__file__).parent.parent.parent / "Server"
if str(_server_dir) not in sys.path:
    sys.path.insert(0, str(_server_dir))
