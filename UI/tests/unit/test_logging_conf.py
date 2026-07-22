"""
Unit tests for UI/observability/logging_conf.py.
"""
import logging
import sys
import pathlib

ui_dir = pathlib.Path(__file__).parent.parent.parent
if str(ui_dir) not in sys.path:
    sys.path.insert(0, str(ui_dir))

import server_bridge  # noqa: F401

from observability.logging_conf import client_logger, configure_client_logging, log_command, log_event, redact


def test_redact_replaces_password_field():
    data = {'username': 'alice', 'password': 'hunter2'}
    assert redact(data) == {'username': 'alice', 'password': '<redacted>'}


def test_configure_client_logging_writes_to_a_per_username_file(tmp_path):
    logger = configure_client_logging('alice_test', log_dir=tmp_path)

    log_command('sent', 'login', {'username': 'alice_test', 'password': 'hunter2'})
    log_event('connected to %s', 'ws://localhost:8765')

    for handler in logger.handlers:
        handler.flush()

    log_file = tmp_path / 'client_alice_test.log'
    assert log_file.exists()
    contents = log_file.read_text(encoding='utf-8')
    assert 'direction=sent' in contents
    assert 'type=login' in contents
    assert 'hunter2' not in contents
    assert 'connected to ws://localhost:8765' in contents

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def test_configure_client_logging_is_idempotent_per_username(tmp_path):
    logger_a = configure_client_logging('bob_test', log_dir=tmp_path)
    handler_count = len(logger_a.handlers)

    logger_b = configure_client_logging('bob_test', log_dir=tmp_path)

    assert logger_a is logger_b
    assert len(logger_b.handlers) == handler_count

    for handler in list(logger_b.handlers):
        logger_b.removeHandler(handler)
        handler.close()


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
