"""
Unit tests for UI/network/protocol.py -- the client-side wire-format mirror
of MultiplayerServer/core/protocol.py.
"""
import pytest

from network.protocol import Envelope, ErrorCode, MalformedEnvelopeError, decode, encode


def test_encode_produces_json_with_type_and_data():
    raw = encode(Envelope(type='ping', data={'a': 1}))
    assert '"type": "ping"' in raw or '"type":"ping"' in raw
    assert '"a": 1' in raw or '"a":1' in raw


def test_decode_round_trips_through_encode():
    envelope = Envelope(type='move', data={'src': [0, 0], 'dest': [0, 3]})
    assert decode(encode(envelope)) == envelope


def test_decode_defaults_missing_data_to_empty_dict():
    assert decode('{"type": "pong"}') == Envelope(type='pong', data={})


def test_decode_rejects_invalid_json():
    with pytest.raises(MalformedEnvelopeError):
        decode('not json')


def test_decode_rejects_non_object_json():
    with pytest.raises(MalformedEnvelopeError):
        decode('[1, 2, 3]')


def test_decode_rejects_missing_type():
    with pytest.raises(MalformedEnvelopeError):
        decode('{"data": {}}')


def test_decode_rejects_empty_type():
    with pytest.raises(MalformedEnvelopeError):
        decode('{"type": ""}')


def test_decode_rejects_non_string_type():
    with pytest.raises(MalformedEnvelopeError):
        decode('{"type": 5}')


def test_decode_rejects_non_object_data():
    with pytest.raises(MalformedEnvelopeError):
        decode('{"type": "ping", "data": [1, 2]}')


def test_error_code_values_match_server_side_reason_strings():
    assert ErrorCode.GAME_OVER.value == 'game_over'
    assert ErrorCode.ILLEGAL_MOVE.value == 'illegal_piece_move'
