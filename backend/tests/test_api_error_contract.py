from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

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
            RuntimeError("postgres://user:password@private-host/db"),
        )


class UnexpectedFailureSession:
    def scalars(self, statement):
        raise RuntimeError(
            "secret internal detail /private/storage/api-key=hidden"
        )


def test_request_validation_uses_stable_error_schema() -> None:
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"question": ""})

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
    assert "password" not in response.text
    assert "private-host" not in response.text
    assert "secret_table" not in response.text


def test_unknown_http_route_uses_safe_fallback_contract() -> None:
    with TestClient(app) as client:
        response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Not Found",
        "code": "http_error",
    }


def test_unexpected_failure_uses_safe_internal_contract() -> None:
    app.dependency_overrides[get_db] = lambda: UnexpectedFailureSession()

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/documents")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Internal server error",
        "code": "internal_error",
    }
    assert "private/storage" not in response.text
    assert "api-key" not in response.text
    assert "secret internal detail" not in response.text
