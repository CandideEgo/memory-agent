"""Structured logging with JSON output and file rotation."""

import json
import logging
import logging.handlers
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Request-scoped correlation ID
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> Optional[str]:
    """Return the current request ID, or None if not set."""
    return request_id_var.get()


def generate_request_id() -> str:
    """Generate a short UUID for a new request."""
    import uuid
    return uuid.uuid4().hex[:12]


class JsonFormatter(logging.Formatter):
    """Structured JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            entry["error"] = str(record.exc_info[1])
        req_id = request_id_var.get()
        if req_id:
            entry["request_id"] = req_id
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(
    level: str = "INFO",
    log_dir: Optional[Path] = None,
    json_file: bool = True,
) -> None:
    """Configure application-wide logging.

    Args:
        level: Log level for console output.
        log_dir: Directory for log files (default: ./logs).
        json_file: Whether to emit structured JSON log files.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    # ── Console handler (stderr, human-readable) ──
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(getattr(logging, level.upper(), logging.INFO))
    console.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    ))
    root.addHandler(console)

    # ── JSON file handler ──
    if json_file and log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        json_handler = logging.handlers.RotatingFileHandler(
            log_dir / "agent.jsonl",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        json_handler.setLevel(logging.INFO)
        json_handler.setFormatter(JsonFormatter())
        root.addHandler(json_handler)

    # ── Error log file ──
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        error_handler = logging.handlers.RotatingFileHandler(
            log_dir / "errors.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.WARNING)
        error_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s\n  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root.addHandler(error_handler)

    for lib in ("httpx", "httpcore", "urllib3", "asyncio"):
        logging.getLogger(lib).setLevel(logging.WARNING)
