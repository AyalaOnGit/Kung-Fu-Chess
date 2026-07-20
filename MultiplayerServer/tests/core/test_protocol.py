import pytest

from core.protocol import Envelope, ErrorCode, MalformedEnvelopeError, decode, encode


def test_encode_then_decode_round_trips():
    envelope = Envelope(type='move', data={'src': [1, 2], 'dest': [3, 4]})
    raw = encode(envelope)
    assert decode(raw) == envelope


def test_decode_defaults_missing_data_to_empty_dict():
    envelope = decode('{"type": "ping"}')
    assert envelope == Envelope(type='ping', data={})


def test_decode_rejects_invalid_json():
    with pytest.raises(MalformedEnvelopeError):
        decode('not json')


def test_decode_rejects_non_object_top_level():
    with pytest.raises(MalformedEnvelopeError):
        decode('[1, 2, 3]')


def test_decode_rejects_missing_type():
    with pytest.raises(MalformedEnvelopeError):
        decode('{"data": {}}')


def test_decode_rejects_non_string_type():
    with pytest.raises(MalformedEnvelopeError):
        decode('{"type": 5}')


def test_decode_rejects_empty_string_type():
    with pytest.raises(MalformedEnvelopeError):
        decode('{"type": ""}')


def test_decode_rejects_non_object_data():
    with pytest.raises(MalformedEnvelopeError):
        decode('{"type": "move", "data": [1, 2]}')


def test_error_code_reuses_engine_reason_strings():
    # commands.py relies on this exact mapping to translate a
    # kungfu_chess CommandResult.reason straight into an ErrorCode.
    assert ErrorCode('game_over') is ErrorCode.GAME_OVER
    assert ErrorCode('motion_in_progress') is ErrorCode.MOTION_IN_PROGRESS
    assert ErrorCode('outside_board') is ErrorCode.OUTSIDE_BOARD
    assert ErrorCode('empty_source') is ErrorCode.EMPTY_SOURCE
    assert ErrorCode('friendly_destination') is ErrorCode.FRIENDLY_DEST
    assert ErrorCode('illegal_piece_move') is ErrorCode.ILLEGAL_MOVE
