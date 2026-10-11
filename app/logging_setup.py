"""JSON-lines logging on stdout (research R8). Every extra field passes through masking.masked,
so a log line can never carry a full account or phone number. configure() is idempotent."""
from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

from app.masking import masked

_STD = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime", "taskName"}
_configured = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": masked(record.getMessage()),
        }
        for k, v in vars(record).items():
            if k not in _STD and not k.startswith("_"):
                out[k] = masked(v, k)
        if record.exc_info:
            out["exc"] = masked(self.formatException(record.exc_info))
        return json.dumps(out, default=str)


def configure(level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for noisy in ("httpx", "httpcore", "openai", "strands"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _configured = True
