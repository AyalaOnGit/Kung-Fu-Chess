"""
Lobby: the Play/Room actions from the spec, which (unlike login) are
described as GUI elements ("Play" Button, a countdown on screen, a popup
message, a Windows dialog with a textbox and Create/Join/Cancel buttons).
Runs after home_shell.py's shell login hands off an authenticated WsClient.

Split in two pieces on purpose:
  - LobbyController: pure decision logic (what command to send, what to do
    with a reply) -- no Tkinter, unit-testable on its own.
  - _LobbyApp / _RoomDialog: a thin Tkinter shell that calls the controller
    and updates widgets from its output.
This mirrors the rest of the codebase's separation of logic from rendering
(kungfu_chess.interaction.Controller vs graphics.renderer, GameFacade vs
ui_components/*).
"""
from __future__ import annotations
import time
import tkinter as tk
from tkinter import messagebox
from dataclasses import dataclass
from typing import Optional

from network.protocol import ErrorCode
from network.ws_client import WsClient
from observability.logging_conf import log_event

_POLL_INTERVAL_MS = 100
_COUNTDOWN_TICK_MS = 250
_QUEUE_TIMEOUT_SECONDS = 60.0


@dataclass
class LobbyResult:
    """Everything NetworkGameFacade needs to start playing."""
    role: str
    room_id: str
    state: dict
    # Populated from match_found/room_created/room_joined when the server
    # knows that seat's identity yet; a room-code creator's opponent seat is
    # still empty (None) until someone joins, since create_room's reply
    # can't know who -- if anyone -- will join later.
    white_username: Optional[str] = None
    white_elo: Optional[int] = None
    black_username: Optional[str] = None
    black_elo: Optional[int] = None


@dataclass
class LobbyOutcome:
    """What LobbyController decided to do with one incoming envelope, for
    the Tk shell to render. All fields default to "nothing to do"."""
    finished: Optional[LobbyResult] = None
    room_id_display: Optional[str] = None
    info_popup: Optional[str] = None
    error_popup: Optional[str] = None
    queue_reset: bool = False
    queue_reset_status: Optional[str] = None
    queue_range_text: Optional[str] = None


class LobbyController:
    """Pure lobby decision logic: no Tkinter/UI dependency."""

    def __init__(self, ws: WsClient):
        self._ws = ws

    def play(self) -> None:
        self._ws.send('queue_join', {})

    def cancel_queue(self) -> None:
        self._ws.send('queue_cancel', {})

    def create_room(self) -> None:
        self._ws.send('create_room', {})

    def join_room(self, room_id: str) -> None:
        self._ws.send('join_room', {'room_id': room_id})

    def handle_envelope(self, envelope) -> LobbyOutcome:
        if envelope.type in ('match_found', 'room_created', 'room_joined'):
            result = LobbyResult(
                role=envelope.data['role'], room_id=envelope.data['room_id'], state=envelope.data['state'],
                white_username=envelope.data.get('white_username'), white_elo=envelope.data.get('white_elo'),
                black_username=envelope.data.get('black_username'), black_elo=envelope.data.get('black_elo'),
            )
            return LobbyOutcome(finished=result, room_id_display=envelope.data['room_id'])
        if envelope.type == 'queued':
            elo, elo_range = envelope.data['elo'], envelope.data['range']
            return LobbyOutcome(queue_range_text=f'ELO range {elo - elo_range}-{elo + elo_range}')
        if envelope.type == 'error':
            return self._handle_error(envelope.data.get('code'))
        return LobbyOutcome()

    @staticmethod
    def _handle_error(code: Optional[str]) -> LobbyOutcome:
        if code == ErrorCode.QUEUE_TIMEOUT.value:
            return LobbyOutcome(
                queue_reset=True, queue_reset_status='No opponent found.',
                info_popup="Couldn't find a match in time. Try again?",
            )
        if code == ErrorCode.ROOM_NOT_FOUND.value:
            return LobbyOutcome(error_popup='No room with that ID.')
        if code == ErrorCode.ALREADY_IN_A_ROOM.value:
            return LobbyOutcome(error_popup='Already in a room.')
        return LobbyOutcome()


class _RoomDialog:
    """Modal Create/Join/Cancel dialog with a room-id textbox, per spec."""

    def __init__(self, parent: tk.Misc, on_create, on_join):
        self._on_create = on_create
        self._on_join = on_join

        self._top = tk.Toplevel(parent)
        self._top.title('Room')
        self._top.geometry('280x150')
        self._top.transient(parent)
        self._top.grab_set()

        tk.Label(self._top, text='Room ID (for Join):').pack(pady=(14, 2))
        self._room_id_var = tk.StringVar()
        tk.Entry(self._top, textvariable=self._room_id_var).pack(pady=2)

        button_frame = tk.Frame(self._top)
        button_frame.pack(pady=14)
        tk.Button(button_frame, text='Create', width=8, command=self._create).grid(row=0, column=0, padx=4)
        tk.Button(button_frame, text='Join', width=8, command=self._join).grid(row=0, column=1, padx=4)
        tk.Button(button_frame, text='Cancel', width=8, command=self._top.destroy).grid(row=0, column=2, padx=4)

    def _create(self) -> None:
        self._top.destroy()
        self._on_create()

    def _join(self) -> None:
        room_id = self._room_id_var.get().strip()
        if not room_id:
            messagebox.showerror('Kung-Fu Chess', 'Enter a room ID to join.')
            return
        self._top.destroy()
        self._on_join(room_id)


class _LobbyApp:
    def __init__(self, ws: WsClient, username: str):
        self._ws = ws
        self._controller = LobbyController(ws)
        self.result: Optional[LobbyResult] = None

        self._queued = False
        self._queue_deadline: Optional[float] = None
        self._queue_range_text = ''

        self._root = tk.Tk()
        self._root.title('Kung-Fu Chess -- Lobby')
        self._root.geometry('360x240')
        self._root.protocol('WM_DELETE_WINDOW', self._on_close)

        self._room_id_var = tk.StringVar(value='Not in a room')
        self._status_var = tk.StringVar(value=f'Signed in as {username}')

        tk.Label(self._root, textvariable=self._room_id_var, font=('Segoe UI', 12, 'bold')).pack(pady=(14, 4))
        tk.Label(self._root, textvariable=self._status_var, fg='gray').pack(pady=(0, 14))

        self._play_button = tk.Button(self._root, text='Play', width=20, command=self._on_play)
        self._play_button.pack(pady=6)
        self._room_button = tk.Button(self._root, text='Room', width=20, command=self._on_room)
        self._room_button.pack(pady=6)
        self._cancel_button = tk.Button(self._root, text='Cancel search', width=20, command=self._on_cancel_queue)

        self._root.after(_POLL_INTERVAL_MS, self._poll)

    def run(self) -> None:
        self._root.mainloop()

    # --- Play ---

    def _on_play(self) -> None:
        self._controller.play()
        self._queued = True
        self._queue_range_text = ''
        self._queue_deadline = time.monotonic() + _QUEUE_TIMEOUT_SECONDS
        self._play_button.config(state=tk.DISABLED)
        self._room_button.config(state=tk.DISABLED)
        self._cancel_button.pack(pady=6)
        self._tick_countdown()

    def _tick_countdown(self) -> None:
        if not self._queued:
            return
        remaining = max(0, int(self._queue_deadline - time.monotonic()))
        suffix = f' ({self._queue_range_text})' if self._queue_range_text else ''
        self._status_var.set(f'Searching for an opponent{suffix}... ({remaining}s)')
        self._root.after(_COUNTDOWN_TICK_MS, self._tick_countdown)

    def _on_cancel_queue(self) -> None:
        self._controller.cancel_queue()
        self._apply_queue_reset('Search cancelled.')

    def _apply_queue_reset(self, status: str) -> None:
        self._queued = False
        self._queue_deadline = None
        self._queue_range_text = ''
        self._status_var.set(status)
        self._play_button.config(state=tk.NORMAL)
        self._room_button.config(state=tk.NORMAL)
        self._cancel_button.pack_forget()

    # --- Room ---

    def _on_room(self) -> None:
        _RoomDialog(self._root, on_create=self._controller.create_room, on_join=self._controller.join_room)

    # --- polling for server replies ---

    def _poll(self) -> None:
        for envelope in self._ws.poll_events():
            self._apply_outcome(self._controller.handle_envelope(envelope))
        if self.result is None:
            self._root.after(_POLL_INTERVAL_MS, self._poll)

    def _apply_outcome(self, outcome: LobbyOutcome) -> None:
        if outcome.queue_range_text is not None:
            self._queue_range_text = outcome.queue_range_text
        if outcome.room_id_display is not None:
            self._room_id_var.set(f'Room: {outcome.room_id_display}')
        if outcome.queue_reset:
            self._apply_queue_reset(outcome.queue_reset_status or '')
        if outcome.info_popup is not None:
            messagebox.showinfo('Kung-Fu Chess', outcome.info_popup)
        if outcome.error_popup is not None:
            messagebox.showerror('Kung-Fu Chess', outcome.error_popup)
        if outcome.finished is not None:
            self.result = outcome.finished
            log_event('lobby finished: role=%s room_id=%s', self.result.role, self.result.room_id)
            self._root.destroy()

    def _on_close(self) -> None:
        self._root.destroy()


def run_lobby(ws: WsClient, username: str) -> Optional[LobbyResult]:
    """Blocks (runs its own Tkinter mainloop) until the user starts a game
    or closes the window. Returns None if closed without starting."""
    app = _LobbyApp(ws, username)
    app.run()
    return app.result
