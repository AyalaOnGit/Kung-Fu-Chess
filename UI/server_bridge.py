"""
Server bridge: inserts server/ onto sys.path.

Must be imported FIRST, before any model/engine import, to ensure
the server modules are available before ui modules try to use them.
"""
import sys
import pathlib

# Add the server directory to sys.path
server_dir = pathlib.Path(__file__).parent.parent / "Server"
if str(server_dir) not in sys.path:
    sys.path.insert(0, str(server_dir))
