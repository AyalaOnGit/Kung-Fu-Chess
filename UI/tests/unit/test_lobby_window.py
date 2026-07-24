"""
Unit tests for lobby_window.py's Tkinter shell (_RoomDialog, _LobbyApp,
run_lobby). LobbyController's pure decision logic is already covered by
test_lobby_controller.py -- this file exercises the thin GUI glue around it.

Real Tk widgets are used throughout (Tk works headlessly fine on this
Windows environment -- no display server needed), so these are true
behavioral tests of widget wiring, not just line-execution padding. The one
thing that must never run for real is a modal messagebox popup (it would
block waiting for a user click) -- lobby_window.py accepts an injectable
`messagebox_module` (defaulting to the real tkinter.messagebox) precisely so
tests can pass a small real fake object instead of ever opening one, mirroring
this codebase's `cv2_module` injection convention in vendor/img.py.

Related assertions are grouped into fewer, larger test functions than usual
here on purpose: each `tk.Tk()` call creates a brand-new Tcl interpreter,
and creating many of them back-to-back in one process was observed to
intermittently fail with a spurious "Can't find a usable init.tcl" TclError
on this machine (a Tcl/filesystem quirk, unrelated to lobby_window.py's own
logic -- reproduced with bare, standalone `tk.Tk()` calls that never touch
this codebase at all) -- keeping the total number of real Tk() root
creations low reduces how often that's hit, and _new_lobby_app()/
_new_tk_root() below retry through it on top of that. _RoomDialog's
Toplevel windows reuse an existing interpreter and don't trigger it, so
those are still one-assertion-per-test.
"""
import time
import tkinter as tk

import pytest

from lobby_window import LobbyOutcome, LobbyResult, _LobbyApp, _RoomDialog, run_lobby
from network.protocol import Envelope


class _FakeWsClient:
    def __init__(self, envelopes=None):
        self.sent = []
        self._queued = list(envelopes or [])

    def send(self, envelope_type, data=None):
        self.sent.append((envelope_type, data or {}))

    def poll_events(self):
        events, self._queued = self._queued, []
        return events


class _FakeMessageBox:
    """Real (non-Mock) stand-in for tkinter.messagebox -- just records
    what would have popped up, instead of blocking on a real modal dialog."""

    def __init__(self):
        self.infos = []
        self.errors = []

    def showinfo(self, title, message):
        self.infos.append((title, message))

    def showerror(self, title, message):
        self.errors.append((title, message))


def _retry_tcl_init_flake(build, attempts=8, delay=0.05):
    """Retry `build()` through the transient Tcl-interpreter-creation flake
    described above. Confirmed (via bare, standalone tk.Tk() calls with no
    lobby_window involvement at all) to surface as tk.TclError from inside
    Tk.__init__'s `_tkinter.create(...)` call, under at least two different
    messages seen in practice ("Can't find a usable init.tcl...", "invalid
    command name \"tcl_findLibrary\""), so this doesn't filter by message
    text -- only by the fact that it's used exclusively around interpreter
    *construction* call sites (_new_tk_root/_new_lobby_app/run_lobby's own
    `_LobbyApp(...)` line), never around later widget interactions, so any
    tk.TclError caught here is this flake, not a real widget-logic bug."""
    last_error = None
    for _ in range(attempts):
        try:
            return build()
        except tk.TclError as e:
            last_error = e
            time.sleep(delay)
    raise last_error


def _new_lobby_app(ws, username, messagebox_module=None):
    return _retry_tcl_init_flake(
        lambda: _LobbyApp(ws, username, messagebox_module=messagebox_module or _FakeMessageBox()))


def _new_tk_root():
    return _retry_tcl_init_flake(tk.Tk)


def _pending_after_count(root) -> int:
    """Real Tcl introspection ('after info' lists pending after-callback
    ids for this interpreter) -- used instead of patching Tk.after to
    observe whether _poll() rescheduled itself."""
    return len(root.tk.call('after', 'info'))


def test_lobby_app_play_cancel_and_poll_flow():
    """One _LobbyApp, walked through its whole Play -> countdown -> cancel
    -> poll/outcome lifecycle in sequence -- each step's assertions build on
    the previous step's, same as a real session would."""
    ws = _FakeWsClient()
    fake_mb = _FakeMessageBox()
    app = _new_lobby_app(ws, 'alice', messagebox_module=fake_mb)
    try:
        # --- initial state ---
        assert app._room_id_var.get() == 'Not in a room'
        assert app._status_var.get() == 'Signed in as alice'
        assert app.result is None
        assert app._queued is False
        app._root.update()  # winfo_ismapped() needs a pumped event loop to see pack()'s effect
        assert app._cancel_button.winfo_ismapped() == 0  # hidden until Play

        # --- Play ---
        app._on_play()
        app._root.update()
        assert ws.sent == [('queue_join', {})]
        assert app._queued is True
        assert str(app._play_button['state']) == 'disabled'
        assert str(app._room_button['state']) == 'disabled'
        assert app._cancel_button.winfo_ismapped() == 1

        # --- countdown ticks, with and without a known ELO range ---
        app._tick_countdown()
        assert 'Searching for an opponent' in app._status_var.get()
        app._queue_range_text = 'ELO range 1100-1300'
        app._tick_countdown()
        assert 'ELO range 1100-1300' in app._status_var.get()

        # --- cancel ---
        app._on_cancel_queue()
        app._root.update()
        assert ws.sent[-1] == ('queue_cancel', {})
        assert app._queued is False
        assert app._status_var.get() == 'Search cancelled.'
        assert str(app._play_button['state']) == 'normal'
        assert str(app._room_button['state']) == 'normal'
        assert app._cancel_button.winfo_ismapped() == 0

        # --- countdown is a no-op once no longer queued (early return) ---
        status_before = app._status_var.get()
        app._tick_countdown()
        assert app._status_var.get() == status_before

        # --- Room dialog is wired to the controller's create/join, and
        # shares this app's (fake) messagebox ---
        app._on_room()
        assert app._room_dialog is not None
        assert app._room_dialog._on_create == app._controller.create_room
        assert app._room_dialog._on_join == app._controller.join_room
        assert app._room_dialog._messagebox is fake_mb
        app._room_dialog._top.destroy()
        app._room_dialog = None

        # --- polling applies outcomes from incoming envelopes ---
        ws._queued = [Envelope(type='queued', data={'elo': 1200, 'range': 100})]
        app._poll()
        assert app._queue_range_text == 'ELO range 1100-1300'

        # --- polling reschedules itself while unfinished, stops once finished ---
        before = _pending_after_count(app._root)
        app._poll()
        assert _pending_after_count(app._root) == before + 1

        app.result = LobbyResult(role='white', room_id='room-1', state={})
        before = _pending_after_count(app._root)
        app._poll()
        assert _pending_after_count(app._root) == before  # no new reschedule
        app.result = None  # don't let this leak into the outcome assertions below

        # --- _apply_outcome's individual effects ---
        app._apply_outcome(LobbyOutcome(room_id_display='room-42'))
        assert app._room_id_var.get() == 'Room: room-42'

        app._apply_outcome(LobbyOutcome(info_popup='Try again?'))
        assert fake_mb.infos == [('Kung-Fu Chess', 'Try again?')]

        app._apply_outcome(LobbyOutcome(error_popup='No room with that ID.'))
        assert fake_mb.errors == [('Kung-Fu Chess', 'No room with that ID.')]

        app._on_play()
        app._apply_outcome(LobbyOutcome(queue_reset=True, queue_reset_status='No opponent found.'))
        assert app._queued is False
        assert app._status_var.get() == 'No opponent found.'
    finally:
        if app._root.winfo_exists():
            app._root.destroy()


def test_apply_outcome_finished_sets_result_and_closes_the_window():
    app = _new_lobby_app(_FakeWsClient(), 'bob')
    result = LobbyResult(role='white', room_id='room-1', state={'pieces': [], 'game_over': False, 'clock_ms': 0})

    app._apply_outcome(LobbyOutcome(finished=result))

    assert app.result is result
    with pytest.raises(tk.TclError):
        app._root.state()  # root has been destroyed


def test_on_close_destroys_the_root():
    app = _new_lobby_app(_FakeWsClient(), 'carol')
    app._on_close()
    with pytest.raises(tk.TclError):
        app._root.state()


def test_room_dialog_create_join_and_blank_id_behaviors():
    root = _new_tk_root()
    root.withdraw()
    try:
        # --- Create: destroys itself and invokes on_create, not on_join ---
        calls = []
        dialog = _RoomDialog(root, on_create=lambda: calls.append('create'),
                              on_join=lambda room_id: calls.append(('join', room_id)))
        dialog._create()
        assert calls == ['create']
        with pytest.raises(tk.TclError):
            dialog._top.state()

        # --- Join: strips whitespace and invokes on_join ---
        calls = []
        dialog = _RoomDialog(root, on_create=lambda: calls.append('create'),
                              on_join=lambda room_id: calls.append(('join', room_id)))
        dialog._room_id_var.set('  abc123  ')
        dialog._join()
        assert calls == [('join', 'abc123')]
        with pytest.raises(tk.TclError):
            dialog._top.state()

        # --- Join with a blank id: error popup, dialog stays open ---
        calls = []
        fake_mb = _FakeMessageBox()
        dialog = _RoomDialog(root, on_create=lambda: calls.append('create'),
                              on_join=lambda room_id: calls.append(('join', room_id)),
                              messagebox_module=fake_mb)
        dialog._room_id_var.set('   ')
        dialog._join()
        assert fake_mb.errors == [('Kung-Fu Chess', 'Enter a room ID to join.')]
        assert calls == []
        assert dialog._top.state() == 'normal'  # still open
        dialog._top.destroy()
    finally:
        root.destroy()


def test_run_lobby_runs_the_mainloop_and_returns_the_apps_result():
    """Real Tk mainloop(), driven for real: _LobbyApp's __init__ schedules
    self._root.after(_POLL_INTERVAL_MS, self._poll) (100ms), and a queued
    match_found envelope makes that first _poll() call self._root.destroy()
    -- which really does end a real mainloop(). No mocking of Tk.mainloop
    needed, just one real ~100ms wait."""
    ws = _FakeWsClient(envelopes=[Envelope(type='match_found', data={
        'role': 'white', 'room_id': 'room-9', 'state': {'pieces': [], 'game_over': False, 'clock_ms': 0},
    })])

    result = _retry_tcl_init_flake(lambda: run_lobby(ws, 'dave', messagebox_module=_FakeMessageBox()))

    assert result is not None
    assert result.role == 'white'
    assert result.room_id == 'room-9'


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
