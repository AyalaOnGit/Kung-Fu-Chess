import game.engine_path  # noqa: F401  (must run before any kungfu_chess import)

import pathlib
import kungfu_chess


def test_kungfu_chess_resolves_under_the_real_server_directory():
    resolved = pathlib.Path(kungfu_chess.__file__).resolve()
    expected_dir = (pathlib.Path(__file__).parent.parent.parent.parent / "Server" / "kungfu_chess").resolve()
    assert resolved.parent == expected_dir
