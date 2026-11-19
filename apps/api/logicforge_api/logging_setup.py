"""Structured JSON logging for production log shipping (Phase 7).

Enabled with LOGICFORGE_LOG_FORMAT=json (default: human-readable console text).
Every log line is a single JSON object: timestamp, level, logger, message, and
any structured fields — ready for any log sink without parsing.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return str(payload).replace("'", '"')


def configure_logging() -> None:
    """Configure root logging once, honoring LOGICFORGE_LOG_FORMAT and LOG_LEVEL."""
    fmt = os.environ.get("LOGICFORGE_LOG_FORMAT", "text").strip().lower()
    level = os.environ.get("LOGICFORGE_LOG_LEVEL", "INFO").strip().upper()
    handler = logging.StreamHandler()
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    handler.setLevel(level)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Uvicorn installs its own handlers; align their level without duplicating output.
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(noisy).handlers = [handler]
        logging.getLogger(noisy).propagate = False
