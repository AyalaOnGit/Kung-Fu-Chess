"""
Client-side logging: mirrors MultiplayerServer/observability/logging_conf.py's
shape (RotatingFileHandler, redact()) so client activity is preserved the same
way server activity now is. Without this, console prints vanish the moment the
game window or shell closes -- MultiplayerServer/logs/server.log and this
module's UI/logs/client_<username>.log now both persist across runs.
"""
from __future__ import annotations
import logging
import pathlib
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Iterable

_LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s: %(message)s'
_DEFAULT_REDACTED_FIELDS = ('password',)
_LOG_DIR = pathlib.Path(__file__).resolve().parent.parent / 'logs'
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3

client_logger = logging.getLogger('kungfu_chess.client')


def redact(data: Dict[str, Any], fields: Iterable[str] = _DEFAULT_REDACTED_FIELDS) -> Dict[str, Any]:
    """Return a copy of data with any of fields replaced by a placeholder."""
    redacted_fields = set(fields)
    return {key: ('<redacted>' if key in redacted_fields else value) for key, value in data.items()}


def configure_client_logging(username: str = 'anonymous', level: int = logging.INFO,
                              log_dir: pathlib.Path = _LOG_DIR) -> logging.Logger:
    """
    Attach a per-username RotatingFileHandler to client_logger and return it.
    Idempotent for a given username -- calling it again (e.g. re-login) won't
    stack duplicate handlers on the same file.
    """
    log_dir = pathlib.Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f'client_{username}.log'

    for handler in list(client_logger.handlers):
        if getattr(handler, 'baseFilename', None) == str(log_file):
            return client_logger

    handler = RotatingFileHandler(log_file, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding='utf-8')
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    client_logger.addHandler(handler)
    client_logger.setLevel(level)
    client_logger.propagate = False
    return client_logger


def log_command(direction: str, envelope_type: str, data: Dict[str, Any]) -> None:
    """direction: 'sent' (command -> server) or 'recv' (event <- server)."""
    client_logger.info('direction=%s type=%s data=%s', direction, envelope_type, redact(data))


def log_event(message: str, *args: Any) -> None:
    """Free-form client activity: connects, disconnects, screen transitions."""
    client_logger.info(message, *args)
