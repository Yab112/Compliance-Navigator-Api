"""Logging for the API: stdout plus an optional size-rotated file.

Settings (environment variables):
- LOG_LEVEL: DEBUG, INFO (default), WARNING, ERROR.
- LOG_FILE: path of the log file (default logs/api.log). Set it empty to log to stdout only,
  which is what the Docker image does (several workers must not rotate one file).
- LOG_MAX_BYTES / LOG_BACKUP_COUNT: rotate after this many bytes, keep this many old files.

We never log request bodies, and the access log drops query strings because links
(password reset, ID verification callbacks) can carry one-time codes there.
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

FORMAT = "%(levelname)s %(asctime)s %(name)s %(funcName)s: %(message)s"

# Chatty libraries that log connection details or raw payloads at DEBUG
NOISY = ("httpx", "httpcore", "multipart", "python_multipart", "botocore",
         "boto3", "urllib3", "faster_whisper", "fastembed")

_MARK = "_cn_handler"


class DropQueryString(logging.Filter):
    """uvicorn access lines: keep the path, drop everything after '?'."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str) and "?" in args[2]:
            record.args = (*args[:2], args[2].split("?", 1)[0], *args[3:])
        return True


def setup_logging() -> None:
    """Safe to call more than once; handlers are only added the first time."""
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    if not any(getattr(h, _MARK, False) for h in root.handlers):
        formatter = logging.Formatter(FORMAT)
        handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
        log_file = os.environ.get("LOG_FILE", "logs/api.log").strip()
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            handlers.append(RotatingFileHandler(
                log_file,
                maxBytes=int(os.environ.get("LOG_MAX_BYTES", str(10 * 1024 * 1024))),
                backupCount=int(os.environ.get("LOG_BACKUP_COUNT", "5")),
                encoding="utf-8",
            ))
        for handler in handlers:
            handler.setFormatter(formatter)
            setattr(handler, _MARK, True)
            root.addHandler(handler)

    for name in NOISY:
        logging.getLogger(name).setLevel(max(level, logging.WARNING))

    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, DropQueryString) for f in access.filters):
        access.addFilter(DropQueryString())
