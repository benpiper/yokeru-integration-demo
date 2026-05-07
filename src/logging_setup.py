import json
import logging
import os
import re
from datetime import UTC, datetime

# Matches phone-like digit runs (with optional +, spaces, dashes, parens, dots).
# Requires at least 7 digits so that short numerics (status codes, attempt
# counters, ports) are not mangled. Lookbehind/lookahead reject hex neighbours
# so we don't shred UUIDs / SHA digests / correlation IDs in log lines.
_PHONE_PATTERN = re.compile(r"(?<![0-9a-fA-F\-])\+?\d[\d\s().\-]{8,}\d(?![0-9a-fA-F\-])")


def redact_phi(text: str) -> str:
    """Best-effort redaction of phone-number-shaped substrings in log output.
    Healthcare context: PHI must not appear in shipped logs even by accident.
    Storage-at-rest is handled separately (see README)."""

    def _mask(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if len(digits) < 7:
            return m.group(0)
        return f"***REDACTED-PHONE({len(digits)}d)***"

    return _PHONE_PATTERN.sub(_mask, text)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "correlation_id": getattr(record, "correlation_id", "N/A"),
            "message": redact_phi(record.getMessage()),
        }
        if record.exc_info:
            log_record["exc_info"] = redact_phi(self.formatException(record.exc_info))
        return json.dumps(log_record)


class TextRedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact_phi(super().format(record))


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "N/A"
        return True


def configure_logging(level: str | None = None, fmt: str | None = None) -> None:
    level_str = (level or os.getenv("YOKERU_LOG_LEVEL") or "INFO").upper()
    fmt_str = (fmt or os.getenv("YOKERU_LOG_FORMAT") or "json").lower()
    log_level = getattr(logging, level_str, logging.INFO)

    root = logging.getLogger()
    root.setLevel(log_level)
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler()
    handler.addFilter(CorrelationIdFilter())
    if fmt_str == "text":
        handler.setFormatter(
            TextRedactingFormatter(
                "%(asctime)s - %(levelname)s - %(name)s - [%(correlation_id)s] - %(message)s"
            )
        )
    else:
        handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    if log_level == logging.DEBUG:
        logging.getLogger("httpx").setLevel(logging.DEBUG)
    else:
        logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
