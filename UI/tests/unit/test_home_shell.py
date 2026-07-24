"""
Unit tests for UI/home_shell.py's login() flow, using a scripted fake
WsClient (no real socket -- ws_client.py's networking is covered separately
by test_ws_client.py).
"""
import home_shell
from network.protocol import Envelope


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


def _prompts(usernames, password='hunter2', prompts_seen=None):
    """Builds real (input_fn, getpass_fn) callables -- no patching of
    builtins.input/getpass.getpass, just plain closures passed directly
    into home_shell.login()'s injectable parameters."""
    inputs = iter(usernames)
    if isinstance(password, str):
        passwords = None
        fixed_password = password
    else:
        passwords = iter(password)
        fixed_password = None

    def input_fn(prompt=''):
        return next(inputs)

    def getpass_fn(prompt=''):
        if prompts_seen is not None:
            prompts_seen.append(prompt)
        return fixed_password if passwords is None else next(passwords)

    return input_fn, getpass_fn


def _login(ws, usernames, password='hunter2', prompts_seen=None, tmp_path=None, wait_timeout=10.0):
    input_fn, getpass_fn = _prompts(usernames, password=password, prompts_seen=prompts_seen)
    return home_shell.login(ws, input_fn=input_fn, getpass_fn=getpass_fn, log_dir=tmp_path, wait_timeout=wait_timeout)


def test_new_username_prompts_to_choose_a_password_and_registers(tmp_path):
    prompts = []
    ws = _ScriptedWsClient({
        'check_username': _check_username(exists=False),
        'register': ('registered', {'username': 'alice', 'elo': 1200}),
    })

    username, resume = _login(ws, ['alice'], prompts_seen=prompts, tmp_path=tmp_path)

    assert username == 'alice'
    assert resume is None
    assert prompts == ['To register, please choose a password: ']
    assert [t for t, _ in ws.sent] == ['check_username', 'register']
    assert ws.sent[1] == ('register', {'username': 'alice', 'password': 'hunter2'})


def test_existing_username_prompts_for_matching_password_and_logs_in(tmp_path):
    prompts = []
    ws = _ScriptedWsClient({
        'check_username': _check_username(exists=True),
        'login': ('logged_in', {'username': 'bob', 'elo': 1210}),
    })

    username, resume = _login(ws, ['bob'], prompts_seen=prompts, tmp_path=tmp_path)

    assert username == 'bob'
    assert resume is None
    assert prompts == ['Please enter matching password: ']
    assert [t for t, _ in ws.sent] == ['check_username', 'login']


def test_login_reconnect_returns_the_state_sync_envelope(tmp_path):
    ws = _ScriptedWsClient({
        'check_username': _check_username(exists=True),
        'login': ('state_sync', {
            'role': 'white', 'room_id': 'abc123',
            'state': {'pieces': [], 'game_over': False, 'clock_ms': 0},
        }),
    })

    username, resume = _login(ws, ['carol'], tmp_path=tmp_path)

    assert username == 'carol'
    assert resume is not None
    assert resume.type == 'state_sync'
    assert resume.data['room_id'] == 'abc123'


def test_login_reprompts_on_empty_username(tmp_path):
    ws = _ScriptedWsClient({
        'check_username': _check_username(exists=False),
        'register': ('registered', {'username': 'dave', 'elo': 1200}),
    })

    username, resume = _login(ws, ['', 'dave'], tmp_path=tmp_path)

    assert username == 'dave'


def test_login_wrong_password_reprompts_until_correct(tmp_path):
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

    username, resume = _login(ws, ['erin', 'erin'], password=['wrongpass', 'hunter2'], tmp_path=tmp_path)

    assert username == 'erin'
    assert attempts['count'] == 2


def test_username_taken_race_reprompts_from_the_top(tmp_path):
    """check_username said the name was free, but someone else grabbed it
    a moment before our register landed -- must loop back cleanly."""
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

    username, resume = _login(ws, ['frank', 'frank2'], tmp_path=tmp_path)

    assert username == 'frank2'
    assert calls['n'] == 2


def test_wait_for_reply_returns_none_on_timeout():
    class _NeverReplies:
        def poll_events(self):
            return []

    result = home_shell._wait_for_reply(_NeverReplies(), 'pong', timeout=0.1)
    assert result is None


def test_login_reprompts_when_check_username_errors(tmp_path):
    """check_username itself coming back as an 'error' envelope (rather
    than timing out, or a normal username_status) must reprompt from the
    top, same as any other recoverable failure."""
    def check_responder(data):
        if data['username'] == 'baduser':
            return 'error', {'code': 'some_error'}
        return 'username_status', {'username': data['username'], 'exists': False}

    ws = _ScriptedWsClient({
        'check_username': check_responder,
        'register': ('registered', {'username': 'gooduser', 'elo': 1200}),
    })

    username, resume = _login(ws, ['baduser', 'gooduser'], tmp_path=tmp_path)

    assert username == 'gooduser'


def test_login_reprompts_when_password_is_empty(tmp_path):
    ws = _ScriptedWsClient({
        'check_username': _check_username(exists=False),
        'register': ('registered', {'username': 'eve', 'elo': 1200}),
    })

    username, resume = _login(ws, ['eve', 'eve'], password=['', 'hunter2'], tmp_path=tmp_path)

    assert username == 'eve'


def test_login_reprompts_after_an_unrecognized_error_code(tmp_path):
    """The final else branch of the post-login/register error handling --
    a code that isn't INVALID_CREDENTIALS or USERNAME_TAKEN -- still just
    reprompts rather than crashing."""
    def login_responder(data):
        if data['username'] == 'unluckyuser':
            return 'error', {'code': 'server_error'}
        return 'logged_in', {'username': data['username'], 'elo': 1200}

    ws = _ScriptedWsClient({
        'check_username': _check_username(exists=True),
        'login': login_responder,
    })

    username, resume = _login(ws, ['unluckyuser', 'luckyuser'], tmp_path=tmp_path)

    assert username == 'luckyuser'


class _FlakyCheckUsernameWsClient:
    """The first check_username send() gets no reply at all (simulating a
    server that's briefly unresponsive) -- every other command replies
    immediately."""

    def __init__(self):
        self.sent = []
        self._queued = []
        self.check_username_calls = 0

    def send(self, envelope_type, data=None):
        data = data or {}
        self.sent.append((envelope_type, data))
        if envelope_type == 'check_username':
            self.check_username_calls += 1
            if self.check_username_calls == 1:
                return  # no reply this attempt
            self._queued.append(Envelope(type='username_status',
                                          data={'username': data['username'], 'exists': False}))
        elif envelope_type == 'register':
            self._queued.append(Envelope(type='registered',
                                          data={'username': data['username'], 'elo': 1200}))

    def poll_events(self):
        events, self._queued = self._queued, []
        return events


def test_login_reprompts_when_check_username_gets_no_reply(tmp_path):
    """_wait_for_reply() timing out on check_username (nothing at all comes
    back) must reprompt, same as an explicit error reply would. Passes a
    short wait_timeout directly (a real injectable parameter) so this test
    doesn't actually take the real 10s default."""
    ws = _FlakyCheckUsernameWsClient()

    username, resume = _login(ws, ['flaky', 'flaky'], tmp_path=tmp_path, wait_timeout=0.05)

    assert username == 'flaky'
    assert ws.check_username_calls == 2


class _FlakyRegisterWsClient:
    """check_username always replies immediately; the first register
    send() gets no reply at all."""

    def __init__(self):
        self.sent = []
        self._queued = []
        self.register_calls = 0

    def send(self, envelope_type, data=None):
        data = data or {}
        self.sent.append((envelope_type, data))
        if envelope_type == 'check_username':
            self._queued.append(Envelope(type='username_status',
                                          data={'username': data['username'], 'exists': False}))
        elif envelope_type == 'register':
            self.register_calls += 1
            if self.register_calls == 1:
                return  # no reply this attempt
            self._queued.append(Envelope(type='registered',
                                          data={'username': data['username'], 'elo': 1200}))

    def poll_events(self):
        events, self._queued = self._queued, []
        return events


def test_login_reprompts_when_register_gets_no_reply(tmp_path):
    ws = _FlakyRegisterWsClient()

    username, resume = _login(ws, ['flaky2', 'flaky2'], tmp_path=tmp_path, wait_timeout=0.05)

    assert username == 'flaky2'
    assert ws.register_calls == 2


class _FakeConnectingWsClient:
    """Stands in for a freshly-constructed WsClient: connect() just flips a
    flag, and the server's greeting ('connected') is already queued so
    connect_and_login()'s own _wait_for_reply(ws, 'connected', ...) finds
    it immediately."""

    def __init__(self, uri):
        self.uri = uri
        self.connect_called = False
        self._queued = [Envelope(type='connected', data={})]

    def connect(self):
        self.connect_called = True

    def poll_events(self):
        events, self._queued = self._queued, []
        return events


def test_connect_and_login_connects_waits_for_the_greeting_then_runs_login():
    created = {}
    login_calls = []

    def fake_ws_client_cls(uri):
        created['ws'] = _FakeConnectingWsClient(uri)
        return created['ws']

    def fake_login(ws):
        login_calls.append(ws)
        return 'alice', None

    ws, username, resume = home_shell.connect_and_login(
        'ws://test', ws_client_cls=fake_ws_client_cls, login_fn=fake_login)

    assert created['ws'].uri == 'ws://test'
    assert created['ws'].connect_called is True
    assert login_calls == [created['ws']]
    assert (ws, username, resume) == (created['ws'], 'alice', None)


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
