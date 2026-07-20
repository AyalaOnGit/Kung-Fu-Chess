import logging

import pytest

from game.events import MoveAccepted
from kungfu_chess.model.piece import Piece, Color, Kind
from kungfu_chess.model.position import Position
from observability.logging_conf import events_logger, make_room_event_logger, redact


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
