"""
Smoke test for UI/main.py's run_local_game()/run_network_game() wiring.

main.py's render loop accepts injectable seams (window, facade,
sound_manager, renderer, hud_renderer, clock, and _run_game_loop's own
perf_counter/sleep_fn) that default to the real thing when omitted -- tests
here pass small real Fake objects through those seams instead of patching
anything. is_open() sequences are used to let exactly one loop iteration (or
zero) run so no real display window is ever opened and no real audio plays.
Everything not explicitly faked (SpriteLoader, GameFacade, BoardRenderer,
HudRenderer, ui_components) is constructed for real, so this test fails if
run_local_game's wiring is broken (wrong constructor args, missing import,
etc.), which is exactly what a smoke test is for.
"""
import importlib.util
import itertools
import sys

import main
from audio.sound_manager import SoundManager
from state.game_events import OpponentJoined


class _FakeWindow:
    """Real (non-Mock) stand-in for graphics.window.Window."""

    def __init__(self, is_open_sequence=None):
        self._is_open_sequence = list(is_open_sequence) if is_open_sequence is not None else None
        self.display_frame_calls = []
        self.close_calls = 0
        self.set_mouse_callback_calls = []

    def is_open(self):
        if self._is_open_sequence is not None:
            return self._is_open_sequence.pop(0) if self._is_open_sequence else False
        return True

    def display_frame(self, frame, fps=None):
        self.display_frame_calls.append((frame, fps))

    def close(self):
        self.close_calls += 1

    def set_mouse_callback(self, callback):
        self.set_mouse_callback_calls.append(callback)


class _RaisingMethodProxy:
    """Wraps a real object, but a single named method raises instead of
    delegating -- a real composition/decorator, not a mock. Every other
    attribute access forwards straight to the wrapped object."""

    def __init__(self, inner, method_name, exc):
        self._inner = inner
        self._method_name = method_name
        self._exc = exc

    def __getattr__(self, name):
        if name == self._method_name:
            def _raise(*args, **kwargs):
                raise self._exc
            return _raise
        return getattr(self._inner, name)


def _muted_sound_manager():
    """A real, disabled SoundManager -- play_start()/on_event() are true
    no-ops (see test_sound_manager.py's coverage of enabled=False), so no
    mocking is needed to keep a headless test run silent."""
    return SoundManager(my_color=None, enabled=False)


def test_module_import_inserts_ui_dir_into_sys_path_if_missing():
    """main.py's module-level `if str(ui_dir) not in sys.path: sys.path.insert(...)`
    only actually inserts when ui_dir isn't already there -- which it
    normally is by the time any test imports this module (conftest.py's own
    path_bootstrap already added it). Loads a second, independent copy of
    main.py by file path (same trick play_online.py's own
    _load_game_main() uses) under a throwaway module name, with ui_dir
    removed from sys.path first, so its module-level code actually takes
    the insert branch -- without disturbing the real 'main' module other
    tests here rely on."""
    ui_dir_str = str(main.ui_dir)
    original_path = list(sys.path)
    try:
        while ui_dir_str in sys.path:
            sys.path.remove(ui_dir_str)
        assert ui_dir_str not in sys.path

        spec = importlib.util.spec_from_file_location('main_reload_probe', main.ui_dir / 'main.py')
        probe_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(probe_module)

        assert ui_dir_str in sys.path
    finally:
        sys.path[:] = original_path
        sys.modules.pop('main_reload_probe', None)


def test_run_local_game_wires_everything_without_raising():
    fake_window = _FakeWindow(is_open_sequence=[False])

    main.run_local_game(window=fake_window, sound_manager=_muted_sound_manager())  # must not raise

    assert len(fake_window.set_mouse_callback_calls) == 1


def test_run_network_game_room_creator_starts_with_opponent_absent():
    """my_role='white' with no black_username yet is the room's creator,
    still alone -- opponent_present must resolve to False so board
    interaction stays blocked. Tested directly against the pure resolver
    function main.py's run_network_game uses, rather than driving the whole
    render loop to observe it."""
    assert main._resolve_opponent_present('white', white_username='alice', black_username=None) is False


def test_run_network_game_joiner_starts_with_opponent_present():
    """my_role='black' arriving to a room that already has a white player
    -- the opponent (white) is present from the joiner's very first frame."""
    assert main._resolve_opponent_present('black', white_username='alice', black_username='bob') is True


def test_run_network_game_viewer_starts_with_opponent_present():
    assert main._resolve_opponent_present('viewer', white_username='alice', black_username='bob') is True


def test_run_local_game_executes_one_full_render_loop_iteration():
    """The other tests here all keep is_open() False from frame one, so the
    while loop's body (rendering, HUD update, display_frame, frame timing)
    never actually runs. Letting it run for exactly one iteration exercises
    that body for real against the real GameFacade/BoardRenderer/HudRenderer
    wiring, with only Window and audio faked out."""
    fake_window = _FakeWindow(is_open_sequence=[True, False])

    main.run_local_game(window=fake_window, sound_manager=_muted_sound_manager())

    assert len(fake_window.display_frame_calls) == 1
    assert fake_window.close_calls == 1


def test_run_local_game_tick_exception_is_caught_and_the_loop_continues():
    """facade.tick() raising must not crash the whole game screen -- it's
    caught, logged, and the frame still renders and displays normally."""
    from kungfu_chess.io.board_factory import standard_board
    from kungfu_chess.engine_builder import build_engine
    from state.game_facade import GameFacade

    fake_window = _FakeWindow(is_open_sequence=[True, False])
    board = standard_board()
    engine = build_engine(board)
    mapper = main._build_mapper(board)
    real_facade = GameFacade(engine, mapper)
    raising_facade = _RaisingMethodProxy(real_facade, 'tick', RuntimeError('boom'))

    main.run_local_game(window=fake_window, sound_manager=_muted_sound_manager(),
                         facade=raising_facade)  # must not raise

    assert len(fake_window.display_frame_calls) == 1  # rendering still happened after the caught error


def test_run_local_game_render_exception_breaks_the_loop():
    """A rendering exception is caught, logged, and breaks out of the loop
    entirely (unlike a tick() exception) -- window.display_frame is never
    reached for that frame."""
    from kungfu_chess.io.board_factory import standard_board
    from kungfu_chess.engine_builder import build_engine
    from state.game_facade import GameFacade
    from graphics.sprite_loader import SpriteLoader
    from graphics.renderer import BoardRenderer
    from ui_config import PIECES_PATH, BOARD_IMAGE_PATH

    fake_window = _FakeWindow()  # is_open() always True -- would loop forever if not for the break
    board = standard_board()
    engine = build_engine(board)
    mapper = main._build_mapper(board)
    facade = GameFacade(engine, mapper)
    sprite_loader = SpriteLoader(main.ui_dir / PIECES_PATH)
    real_renderer = BoardRenderer(board, sprite_loader, str(main.ui_dir / BOARD_IMAGE_PATH), facade, mapper)
    raising_renderer = _RaisingMethodProxy(real_renderer, 'render', RuntimeError('boom'))

    main.run_local_game(window=fake_window, sound_manager=_muted_sound_manager(),
                         facade=facade, renderer=raising_renderer)  # must not raise, must terminate

    assert fake_window.display_frame_calls == []
    assert fake_window.close_calls == 1


class _FakeNetworkFacade:
    """Real (non-Mock) stand-in for NetworkGameFacade -- just enough surface
    for _run_game_loop to drive it: subscribe() records callbacks so a test
    can invoke them directly, the rest are cheap no-ops."""

    def __init__(self, board, my_color=None):
        self.board = board
        self.my_color = my_color
        self.subscribed = []

    def subscribe(self, callback):
        self.subscribed.append(callback)

    def request_click(self, x, y):
        return False

    def request_jump(self, x, y):
        pass

    def tick(self, dt_ms):
        pass

    def get_selected_pos(self):
        return None

    def get_cooldown_ratio(self, *args, **kwargs):
        return 0.0

    def get_pending_motion(self, *args, **kwargs):
        return None


class _FakeHudRenderer:
    """Real (non-Mock) stand-in for HudRenderer -- records set_player calls,
    no-ops everything else _run_game_loop calls on it."""

    def __init__(self):
        self.set_player_calls = []

    def set_pieces_dir(self, path):
        pass

    def set_room_id(self, room_id):
        pass

    def set_my_role(self, role):
        pass

    def set_moves(self, moves):
        pass

    def update_score(self, **kwargs):
        pass

    def set_game_over(self, info):
        pass

    def set_network_status(self, message):
        pass

    def set_player(self, role, username, elo):
        self.set_player_calls.append((role, username, elo))

    def render(self, board_frame):
        return board_frame


def test_opponent_joined_event_updates_the_hud_only_for_opponent_joined_events():
    """main.py's on_opponent_joined callback (subscribed in _run_game_loop)
    drops the 'Waiting for opponent...' placeholder as soon as the server
    reports the seat filled, without waiting for the next board-changing
    event. Captured directly off the fake facade's recorded subscribe()
    calls rather than driving a whole render loop iteration for it."""
    from kungfu_chess.model.board import Board

    fake_window = _FakeWindow(is_open_sequence=[False])
    fake_facade = _FakeNetworkFacade(board=Board(width=8, height=8))
    fake_hud = _FakeHudRenderer()

    main.run_network_game(
        ws_client=None, mapper=main._build_mapper(Board(width=8, height=8)),
        my_role='white', room_id='room1', initial_state={'pieces': [], 'game_over': False},
        white_username='alice', black_username=None,
        facade=fake_facade, window=fake_window, sound_manager=_muted_sound_manager(),
        hud_renderer=fake_hud,
    )

    on_opponent_joined = fake_facade.subscribed[-1]

    on_opponent_joined(OpponentJoined(role='black', username='bob', elo=1200))
    assert fake_hud.set_player_calls == [('black', 'bob', 1200)]

    fake_hud.set_player_calls.clear()
    on_opponent_joined(object())  # any other event type is ignored
    assert fake_hud.set_player_calls == []


def test_run_network_game_render_loop_reports_network_status():
    """Only run_network_game wires up a NetworkStatusPanel, so the
    `if network_status_panel is not None:` branches (both the per-tick
    update and the HUD's set_network_status call) only run via this path.
    Uses a real NetworkGameFacade (not the bare fake above, whose .board
    wouldn't be a real, populated Board and would blow up BoardRenderer) so
    the loop body renders a real frame successfully."""
    from kungfu_chess.interaction.board_mapper import BoardMapper
    from network.network_game_facade import NetworkGameFacade

    class _FakeWsClient:
        def send(self, envelope_type, data=None):
            pass

        def poll_events(self):
            return []

    state = {
        'pieces': [
            {'id': 1, 'color': 'w', 'kind': 'K', 'cell': [7, 4], 'state': 'idle'},
            {'id': 2, 'color': 'b', 'kind': 'K', 'cell': [0, 4], 'state': 'idle'},
        ],
        'game_over': False, 'clock_ms': 0,
    }
    mapper = BoardMapper(width=8, height=8, offset_x=0, offset_y=0)
    facade = NetworkGameFacade(_FakeWsClient(), mapper, state, 'white', opponent_present=True)

    fake_window = _FakeWindow(is_open_sequence=[True, False])

    main.run_network_game(
        ws_client=_FakeWsClient(), mapper=mapper, my_role='white', room_id='room1',
        initial_state=state, white_username='alice', black_username='bob',
        facade=facade, window=fake_window, sound_manager=_muted_sound_manager(),
    )

    assert len(fake_window.display_frame_calls) == 1


class _FakeClock:
    """Real (non-Mock) stand-in for AnimationClock -- returns a fixed
    sequence of tick() values."""

    def __init__(self, tick_values):
        self._values = list(tick_values)

    def tick(self):
        return self._values.pop(0) if self._values else 0.0


def test_run_local_game_caps_dt_ms_at_200():
    """AnimationClock.tick() reporting more than 200ms (e.g. a debugger
    pause, or the OS starving the process for a moment) must be clamped to
    200ms rather than handed straight to facade.tick()/rendering -- avoids a
    single huge, jarring animation jump."""
    from kungfu_chess.io.board_factory import standard_board
    from kungfu_chess.engine_builder import build_engine
    from state.game_facade import GameFacade

    class _TickSpyFacade:
        def __init__(self, inner):
            self._inner = inner
            self.tick_calls = []

        def tick(self, dt_ms):
            self.tick_calls.append(dt_ms)
            return self._inner.tick(dt_ms)

        def __getattr__(self, name):
            return getattr(self._inner, name)

    fake_window = _FakeWindow(is_open_sequence=[True, False])
    board = standard_board()
    engine = build_engine(board)
    mapper = main._build_mapper(board)
    spy_facade = _TickSpyFacade(GameFacade(engine, mapper))

    main.run_local_game(window=fake_window, sound_manager=_muted_sound_manager(),
                         facade=spy_facade, clock=_FakeClock([500.0]))

    assert spy_facade.tick_calls == [200]


def test_run_game_loop_sleeps_when_the_frame_finishes_before_the_target():
    from kungfu_chess.io.board_factory import standard_board
    from kungfu_chess.engine_builder import build_engine
    from state.game_facade import GameFacade

    fake_window = _FakeWindow(is_open_sequence=[True, False])
    board = standard_board()
    engine = build_engine(board)
    mapper = main._build_mapper(board)
    facade = GameFacade(engine, mapper)
    perf_values = itertools.count(0.0, 0.001)
    sleep_calls = []

    main._run_game_loop(facade, board, mapper, _muted_sound_manager(),
                         window=fake_window, perf_counter=lambda: next(perf_values),
                         sleep_fn=sleep_calls.append)

    assert len(sleep_calls) == 1
    assert sleep_calls[0] > 0


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
