"""
Wire protocol mirror of MultiplayerServer/core/protocol.py.

Deliberately duplicated rather than imported: MultiplayerServer's own
subpackages (core, game, network, db, observability, ...) are meant to be
put directly on sys.path as top-level modules (see MultiplayerServer's own
dev_client.py) -- doing that from the UI side would collide with UI's own
top-level packages of the same name (this file's own package is
UI/network/, and UI/observability/ already exists). The wire format itself
is tiny and stable, so a client-side copy is cheaper than resolving that
collision.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from enum import Enum


class MalformedEnvelopeError(Exception):
    """Raised when raw wire data cannot be decoded into a valid Envelope."""


class ErrorCode(Enum):
    """Mirrors MultiplayerServer/core/protocol.py::ErrorCode exactly."""
    OK                  = 'ok'
    MALFORMED_COMMAND   = 'malformed_command'
    UNKNOWN_COMMAND     = 'unknown_command'
    USERNAME_TAKEN      = 'username_taken'
    INVALID_CREDENTIALS = 'invalid_credentials'
    NOT_AUTHENTICATED   = 'not_authenticated'
    NOT_IN_A_MATCH      = 'not_in_a_match'
    ALREADY_IN_A_ROOM   = 'already_in_a_room'
    ROOM_NOT_FOUND      = 'room_not_found'
    QUEUE_TIMEOUT       = 'queue_timeout'
    VIEWER_READ_ONLY    = 'viewer_read_only'
    NOT_YOUR_PIECE      = 'not_your_piece'
    PIECE_MISMATCH      = 'piece_mismatch'
    EMPTY_SOURCE        = 'empty_source'
    GAME_OVER           = 'game_over'
    MOTION_IN_PROGRESS  = 'motion_in_progress'
    OUTSIDE_BOARD       = 'outside_board'
    FRIENDLY_DEST       = 'friendly_destination'
    ILLEGAL_MOVE        = 'illegal_piece_move'


@dataclass(frozen=True)
class Envelope:
    """A decoded wire message: a type tag plus a flat data payload."""
    type: str
    data: dict = field(default_factory=dict)


def encode(envelope: Envelope) -> str:
    """Serialize an Envelope to a JSON string ready to send over a socket."""
    return json.dumps({'type': envelope.type, 'data': envelope.data})


def decode(raw: str) -> Envelope:
    """
    Parse raw text received from a socket into an Envelope.

    :raises MalformedEnvelopeError: if raw isn't valid JSON, isn't an object,
        is missing a string 'type' field, or has a non-object 'data' field.
    """
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        raise MalformedEnvelopeError(f'invalid JSON: {e}') from e

    if not isinstance(payload, dict):
        raise MalformedEnvelopeError('envelope must be a JSON object')

    msg_type = payload.get('type')
    if not isinstance(msg_type, str) or not msg_type:
        raise MalformedEnvelopeError("envelope missing non-empty string 'type' field")

    data = payload.get('data', {})
    if not isinstance(data, dict):
        raise MalformedEnvelopeError("envelope 'data' field must be an object")

    return Envelope(type=msg_type, data=data)
