"""
Unit tests for UI/home_shell.py's login() flow, using a scripted fake
WsClient (no real socket -- ws_client.py's networking is covered separately
by test_ws_client.py).
"""
import sys
import pathlib

ui_dir = pathlib.Path(__file__).parent.parent.parent
if str(ui_dir) not in sys.path:
    sys.path.insert(0, str(ui_dir))

import server_bridge  # noqa: F401

import pytest

import home_shell
from network.protocol import Envelope


@pytest.fixture(autouse=True)
def _isolate_client_logs(monkeypatch, tmp_path):
    """login() calls configure_client_logging() for real on success -- keep
    its output under tmp_path instead of polluting UI/logs/ every test run."""
    original = home_shell.configure_client_logging
    monkeypatch.setattr(home_shell, 'configure_client_logging',
                         lambda username, **kw: original(username, log_dir=tmp_path))


class _ScriptedWsClient:
    """script: dict mapping sent envelope_type -> (reply_type, reply_data)
    or a callable(data) -> (reply_type, reply_data). Replies are enqueued
    synchronously inside send(), so _wait_for_reply's first poll finds them
    immediately -- no real sleeping in these tests."""

    def __init__(self, script):
        self._script = script
        self._queued = []
        self.sent = []

    def send(self, envelope_type, data=None):
        data = data or {}
        self.sent.append((envelope_type, data))
        responder = self._script.get(envelope_type)
        if responder is None:
            return
        reply_type, reply_data = responder(data) if callable(responder) else responder
        self._queued.append(Envelope(type=reply_type, data=reply_data))

    def poll_events(self):
        events, self._queued = self._queued, []
        return events


def _check_username(exists: bool):
    return lambda data: ('username_status', {'username': data['username'], 'exists': exists})


def _patch_prompts(monkeypatch, usernames, password='hunter2', prompts_seen=None):
    inputs = iter(usernames)
    monkeypatch.setattr('builtins.input', lambda prompt='': next(inputs))
    if isinstance(password, str):
        passwords = None
        fixed_password = password
    else:
        passwords = iter(password)
        fixed_password = None

    def fake_getpass(prompt=''):
        if prompts_seen is not None:
            prompts_seen.append(prompt)
        return fixed_password if passwords is None else next(passwords)

    monkeypatch.setattr('getpass.getpass', fake_getpass)


def test_new_username_prompts_to_choose_a_password_and_registers(monkeypatch):
    prompts = []
    _patch_prompts(monkeypatch, ['alice'], prompts_seen=prompts)
    ws = _ScriptedWsClient({
        'check_username': _check_username(exists=False),
        'register': ('registered', {'username': 'alice', 'elo': 1200}),
    })

    username, resume = home_shell.login(ws)

    assert username == 'alice'
    assert resume is None
    assert prompts == ['To register, please choose a password: ']
    assert [t for t, _ in ws.sent] == ['check_username', 'register']
    assert ws.sent[1] == ('register', {'username': 'alice', 'password': 'hunter2'})


def test_existing_username_prompts_for_matching_password_and_logs_in(monkeypatch):
    prompts = []
    _patch_prompts(monkeypatch, ['bob'], prompts_seen=prompts)
    ws = _ScriptedWsClient({
        'check_username': _check_username(exists=True),
        'login': ('logged_in', {'username': 'bob', 'elo': 1210}),
    })

    username, resume = home_shell.login(ws)

    assert username == 'bob'
    assert resume is None
    assert prompts == ['Please enter matching password: ']
    assert [t for t, _ in ws.sent] == ['check_username', 'login']


def test_login_reconnect_returns_the_state_sync_envelope(monkeypatch):
    _patch_prompts(monkeypatch, ['carol'])
    ws = _ScriptedWsClient({
        'check_username': _check_username(exists=True),
        'login': ('state_sync', {
            'role': 'white', 'room_id': 'abc123',
            'state': {'pieces': [], 'game_over': False, 'clock_ms': 0},
        }),
    })

    username, resume = home_shell.login(ws)

    assert username == 'carol'
    assert resume is not None
    assert resume.type == 'state_sync'
    assert resume.data['room_id'] == 'abc123'


def test_login_reprompts_on_empty_username(monkeypatch):
    _patch_prompts(monkeypatch, ['', 'dave'])
    ws = _ScriptedWsClient({
        'check_username': _check_username(exists=False),
        'register': ('registered', {'username': 'dave', 'elo': 1200}),
    })

    username, resume = home_shell.login(ws)

    assert username == 'dave'


def test_login_wrong_password_reprompts_until_correct(monkeypatch):
    _patch_prompts(monkeypatch, ['erin', 'erin'], password=['wrongpass', 'hunter2'])
    attempts = {'count': 0}

    def login_responder(data):
        attempts['count'] += 1
        if data['password'] == 'hunter2':
            return 'logged_in', {'username': 'erin', 'elo': 1200}
        return 'error', {'code': 'invalid_credentials'}

    ws = _ScriptedWsClient({
        'check_username': _check_username(exists=True),
        'login': login_responder,
    })

    username, resume = home_shell.login(ws)

    assert username == 'erin'
    assert attempts['count'] == 2


def test_username_taken_race_reprompts_from_the_top(monkeypatch):
    """check_username said the name was free, but someone else grabbed it
    a moment before our register landed -- must loop back cleanly."""
    _patch_prompts(monkeypatch, ['frank', 'frank2'])
    ws = _ScriptedWsClient({
        'check_username': _check_username(exists=False),
        'register': ('error', {'code': 'username_taken'}),
    })
    # Second time around, frank2 registers cleanly.
    calls = {'n': 0}

    def check_responder(data):
        calls['n'] += 1
        return 'username_status', {'username': data['username'], 'exists': False}
    ws._script['check_username'] = check_responder

    def register_responder(data):
        if data['username'] == 'frank':
            return 'error', {'code': 'username_taken'}
        return 'registered', {'username': 'frank2', 'elo': 1200}
    ws._script['register'] = register_responder

    username, resume = home_shell.login(ws)

    assert username == 'frank2'
    assert calls['n'] == 2


def test_wait_for_reply_returns_none_on_timeout():
    class _NeverReplies:
        def poll_events(self):
            return []

    result = home_shell._wait_for_reply(_NeverReplies(), 'pong', timeout=0.1)
    assert result is None


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
