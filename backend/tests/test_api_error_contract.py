from __future__ import annotations

from datetime import UTC, datetime
import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.dependencies import (
    get_embedding_provider_dependency,
    get_generation_provider_dependency,
)
from app.core.database import get_db
from app.main import app
from app.models.document import Document, DocumentStatus


class MissingDocumentSession:
    def get(self, model, document_id: int):
        return None


class UnavailableDatabaseSession:
    def scalars(self, statement):
        raise OperationalError(
            "SELECT secret_table",
            {},
            RuntimeError("sensitive-database-marker"),
        )


class UnexpectedFailureSession:
    def scalars(self, statement):
        raise RuntimeError("secret-internal-marker")


def test_request_validation_uses_stable_error_schema() -> None:
    # Dependency resolution precedes body validation in FastAPI. Keep this
    # test independent of external API credentials and provider setup.
    app.dependency_overrides[get_embedding_provider_dependency] = lambda: object()
    app.dependency_overrides[get_generation_provider_dependency] = lambda: object()
    app.dependency_overrides[get_db] = lambda: object()

    try:
        with TestClient(app) as client:
            response = client.post("/api/chat", json={"question": ""})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Request validation failed",
        "code": "validation_error",
    }


def test_missing_document_uses_stable_error_code() -> None:
    app.dependency_overrides[get_db] = lambda: MissingDocumentSession()

    try:
        with TestClient(app) as client:
            response = client.get("/api/documents/999")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Document not found",
        "code": "document_not_found",
    }


def test_database_failure_is_safe_and_does_not_leak_connection_details() -> None:
    app.dependency_overrides[get_db] = (
        lambda: UnavailableDatabaseSession()
    )

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/documents")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Database is temporarily unavailable",
        "code": "database_unavailable",
    }
    assert "sensitive-database-marker" not in response.text
    assert "secret_table" not in response.text


def test_unknown_http_route_uses_safe_fallback_contract() -> None:
    with TestClient(app) as client:
        response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Not Found",
        "code": "http_error",
    }



def test_application_error_log_uses_safe_structured_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app.dependency_overrides[get_db] = (
        lambda: UnavailableDatabaseSession()
    )

    try:
        with caplog.at_level(
            logging.ERROR,
            logger="app.api.errors",
        ):
            with TestClient(
                app,
                raise_server_exceptions=False,
            ) as client:
                response = client.get("/api/documents")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503

    record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "application.error"
    )
    assert record.error_code == "database_unavailable"
    assert record.http_status == 503
    assert record.error_type == "OperationalError"
    assert "sensitive-database-marker" not in caplog.text
    assert "secret_table" not in caplog.text


def test_internal_failure_log_is_structured_without_secret_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app.dependency_overrides[get_db] = lambda: UnexpectedFailureSession()

    try:
        with caplog.at_level(
            logging.ERROR,
            logger="app.api.errors",
        ):
            with TestClient(
                app,
                raise_server_exceptions=False,
            ) as client:
                response = client.get("/api/documents")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Internal server error",
        "code": "internal_error",
    }

    record = next(
        record
        for record in caplog.records
        if getattr(record, "error_code", None) == "internal_error"
    )
    assert record.http_status == 500
    assert record.error_type == "RuntimeError"
    assert '"event":"application.error"' in record.getMessage()
    assert "secret-internal-marker" not in caplog.text
