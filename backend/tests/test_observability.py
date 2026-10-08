import json
import logging

from app.core.observability import log_event


def test_log_event_emits_safe_json_and_drops_unapproved_fields(
    caplog,
) -> None:
    logger = logging.getLogger("app.tests.observability")

    with caplog.at_level(logging.INFO, logger=logger.name):
        log_event(
            logger,
            logging.INFO,
            "test.event",
            document_id=42,
            duration_ms=12.5,
            secret="do-not-log",
            question="private user question",
        )

    record = caplog.records[-1]
    payload = json.loads(record.getMessage())

    assert payload == {
        "document_id": 42,
        "duration_ms": 12.5,
        "event": "test.event",
    }
    assert record.document_id == 42
    assert record.duration_ms == 12.5
    assert "do-not-log" not in caplog.text
    assert "private user question" not in caplog.text
