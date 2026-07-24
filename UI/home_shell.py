"""
Home screen: shell/CLI login step (per spec: "do it in a shell, not via
GUI"). Prompts for a username + password over stdin, registers a new
account or logs an existing one in against MultiplayerServer, and hands the
authenticated WsClient off to the Tkinter lobby (lobby_window.py) for the
Play/Room steps.
"""
from __future__ import annotations
import getpass
import sys
import time
from typing import Optional, Tuple

from network.protocol import Envelope, ErrorCode
from network.ws_client import WsClient
from observability.logging_conf import configure_client_logging, log_event

DEFAULT_URI = 'ws://localhost:8765'
_REPLY_TIMEOUT_S = 10.0


def _wait_for_reply(ws: WsClient, *expected_types: str, timeout: float = _REPLY_TIMEOUT_S) -> Optional[Envelope]:
    """Block until an envelope of one of expected_types arrives (or timeout)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for envelope in ws.poll_events():
            if envelope.type in expected_types:
                return envelope
        time.sleep(0.05)
    return None


def login(ws: WsClient, input_fn=input, getpass_fn=getpass.getpass,
          log_dir: Optional[str] = None, wait_timeout: float = _REPLY_TIMEOUT_S) -> Tuple[str, Optional[Envelope]]:
    """
    Terminal-only login flow. Checks whether the entered username is
    already registered (check_username) before ever asking for a password,
    so the password prompt itself can say which case this is:
    "Please enter matching password" for an existing account, or
    "To register, please choose a password" for a new one.

    :param input_fn: injectable stand-in for the builtin input(), for tests.
    :param getpass_fn: injectable stand-in for getpass.getpass(), for tests.
    :param log_dir: passed through to configure_client_logging() on success;
        None uses that function's own default (the real log directory).
    :param wait_timeout: passed through to every _wait_for_reply() call, so
        tests can use a short timeout instead of the real 10s default.
    :return: (username, resume_envelope). resume_envelope is the
        'state_sync' envelope if this login reclaimed an in-progress game
        (server-side reconnect within the grace period) -- in that case the
        caller should skip the lobby and rejoin the game screen directly.
        None for a normal login/registration.
    """
    print('=== Kung-Fu Chess: sign in ===')
    while True:
        username = input_fn('Username: ').strip()
        if not username:
            print('Username is required.')
            continue

        ws.send('check_username', {'username': username})
        reply = _wait_for_reply(ws, 'username_status', 'error', timeout=wait_timeout)
        if reply is None:
            print('Server did not respond -- is MultiplayerServer running?')
            continue
        if reply.type == 'error':
            print(f"Could not check that username: {reply.data.get('code')}")
            continue

        exists = reply.data.get('exists', False)
        prompt = 'Please enter matching password: ' if exists else 'To register, please choose a password: '
        password = getpass_fn(prompt)
        if not password:
            print('Password is required.')
            continue

        command = 'login' if exists else 'register'
        ws.send(command, {'username': username, 'password': password})
        reply = _wait_for_reply(ws, 'registered', 'logged_in', 'state_sync', 'error', timeout=wait_timeout)
        if reply is None:
            print('Server did not respond.')
            continue

        if reply.type == 'registered':
            print(f"Registered as {reply.data['username']} (elo {reply.data['elo']}).")
            _finish_login(username, log_dir=log_dir)
            return username, None

        if reply.type == 'logged_in':
            print(f"Welcome back, {username}.")
            _finish_login(username, log_dir=log_dir)
            return username, None

        if reply.type == 'state_sync':
            print(f"Welcome back, {username} -- rejoining your in-progress game.")
            _finish_login(username, log_dir=log_dir)
            return username, reply

        code = reply.data.get('code')
        if code == ErrorCode.INVALID_CREDENTIALS.value:
            print('Wrong password, try again.')
        elif code == ErrorCode.USERNAME_TAKEN.value:
            # Race: someone else registered this exact username between our
            # check and our register -- send them back to try again.
            print('That username was just taken -- try a different one, or log in instead.')
        else:
            print(f"{'Login' if exists else 'Registration'} failed: {code}")


def _finish_login(username: str, log_dir: Optional[str] = None) -> None:
    if log_dir is not None:
        configure_client_logging(username, log_dir=log_dir)
    else:
        configure_client_logging(username)
    log_event('logged in as %s', username)


def connect_and_login(uri: str = DEFAULT_URI, ws_client_cls=WsClient,
                       login_fn=login) -> Tuple[WsClient, str, Optional[Envelope]]:
    """Connect to MultiplayerServer and run the shell login flow. Returns
    (ws_client, username, resume_envelope) -- see login()'s docstring for
    resume_envelope.

    :param ws_client_cls: injectable stand-in for WsClient, for tests.
    :param login_fn: injectable stand-in for login(), for tests.
    """
    print(f'Connecting to {uri} ...')
    ws = ws_client_cls(uri)
    ws.connect()
    _wait_for_reply(ws, 'connected', timeout=5.0)  # server's greeting on accept
    log_event('connected to %s', uri)

    username, resume_envelope = login_fn(ws)
    return ws, username, resume_envelope


if __name__ == '__main__':
    uri = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URI
    try:
        ws_client, logged_in_username, resume = connect_and_login(uri)
        print(f'Logged in as {logged_in_username}.')
        if resume is not None:
            print(f"Would rejoin room {resume.data['room_id']} as {resume.data['role']}.")
        ws_client.close()
    except KeyboardInterrupt:
        pass
