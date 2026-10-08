from __future__ import annotations

import logging
from time import perf_counter
from typing import Any


SAFE_LOG_FIELDS = frozenset(
    {
        "document_id",
        "status",
        "chunk_count",
        "result_count",
        "duration_ms",
        "provider",
        "operation",
        "error_type",
        "error_code",
        "http_status",
    }
)


def elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 2)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    safe_fields = {
        key: value
        for key, value in fields.items()
        if key in SAFE_LOG_FIELDS
        and isinstance(value, (str, int, float, bool, type(None)))
    }

    logger.log(
        level,
        event,
        extra={
            "event": event,
            **safe_fields,
        },
    )
