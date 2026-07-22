import logging

import pytest

from game.events import MoveAccepted
from kungfu_chess.model.piece import Piece, Color, Kind
from kungfu_chess.model.position import Position
from observability.logging_conf import (
    commands_logger, configure_logging, events_logger, log_command, make_room_event_logger, redact,
)


def test_redact_replaces_default_credential_fields():
    data = {'username': 'alice', 'password': 'hunter2'}
    assert redact(data) == {'username': 'alice', 'password': '<redacted>'}


def test_redact_does_not_mutate_the_original():
    data = {'username': 'alice', 'password': 'hunter2'}
    redact(data)
    assert data == {'username': 'alice', 'password': 'hunter2'}


def test_redact_with_explicit_fields():
    data = {'a': 1, 'b': 2, 'c': 3}
    assert redact(data, fields=('b', 'c')) == {'a': 1, 'b': '<redacted>', 'c': '<redacted>'}


def test_redact_leaves_data_without_matching_fields_untouched():
    data = {'src': [0, 0], 'dest': [0, 3]}
    assert redact(data) == data


def test_log_command_redacts_password_and_tags_session_and_direction(caplog):
    with caplog.at_level(logging.INFO, logger=commands_logger.name):
        log_command('recv', 'session-1', 'login', {'username': 'alice', 'password': 'hunter2'})

    assert len(caplog.records) == 1
    message = caplog.records[0].message
    assert 'session=session-1' in message
    assert 'direction=recv' in message
    assert 'type=login' in message
    assert 'hunter2' not in message
    assert "'password': '<redacted>'" in message


def test_configure_logging_creates_a_rotating_file_handler(tmp_path):
    configure_logging(log_dir=str(tmp_path), log_file='server.log')
    logging.getLogger(__name__).info('hello from test')

    log_file = tmp_path / 'server.log'
    assert log_file.exists()
    assert 'hello from test' in log_file.read_text(encoding='utf-8')

    # Clean up the handler we just registered on the root logger so it
    # doesn't leak into (or hold a file lock across) other tests.
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, 'baseFilename', None) == str(log_file):
            root.removeHandler(handler)
            handler.close()


@pytest.mark.asyncio
async def test_room_event_logger_logs_with_room_id_tagged(caplog):
    piece = Piece(id=1, color=Color.WHITE, kind=Kind.ROOK, cell=Position(0, 3))
    event = MoveAccepted(piece=piece, src=Position(0, 0), dest=Position(0, 3))
    handler = make_room_event_logger('room-abc')

    with caplog.at_level(logging.INFO, logger=events_logger.name):
        await handler(event)

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert 'room_id=room-abc' in record.message
    assert 'move_accepted' in record.message
