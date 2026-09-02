import json
import logging
import re
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


REDACTED = "***REDACTED***"
SENSITIVE_KEYS = {
    "api_key", "apikey", "api-key", "x-mbx-apikey", "api_secret",
    "apisecret", "secret", "signature", "authorization",
}
SENSITIVE_PATTERN = re.compile(
    r"(?i)(api[_-]?key|api[_-]?secret|secret|signature|authorization|x-mbx-apikey)"
    r"(\s*[=:]\s*|\s+)([^\s,;}&]+)"
)
BEARER_PATTERN = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+")


def sanitize(value: Any) -> Any:
    """Recursively redact credentials from structured or plain log data."""
    if isinstance(value, dict):
        return {
            key: REDACTED if str(key).lower() in SENSITIVE_KEYS else sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        sanitized = [sanitize(item) for item in value]
        return tuple(sanitized) if isinstance(value, tuple) else sanitized
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if isinstance(parsed, (dict, list)):
            return json.dumps(sanitize(parsed), ensure_ascii=False, default=str)
        text = BEARER_PATTERN.sub(rf"\1{REDACTED}", value)
        return SENSITIVE_PATTERN.sub(
            lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", text
        )
    return value


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = sanitize(record.msg)
        if record.args:
            record.args = sanitize(record.args)
        return True


class UTCFormatter(logging.Formatter):
    converter = time.gmtime

    def formatTime(self, record, datefmt=None):
        return time.strftime("%Y-%m-%d %H:%M:%S UTC", self.converter(record.created))

    def format(self, record: logging.LogRecord) -> str:
        # A final pass also sanitizes exception text produced by logging.
        return sanitize(super().format(record))


def get_logger(
    name: str = "trading_bot",
    level: str = "INFO",
    log_file: str = "logs/trading_bot.log",
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    if getattr(logger, "_trading_bot_configured", False):
        return logger

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(UTCFormatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    ))
    handler.addFilter(SensitiveDataFilter())
    logger.addHandler(handler)
    logger._trading_bot_configured = True
    return logger


def log_event(logger: logging.Logger, level: int, event: str, **context: Any) -> None:
    payload = {"event": event, **context}
    logger.log(level, json.dumps(sanitize(payload), ensure_ascii=False, default=str))
