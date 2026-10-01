from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.services.storage_service import StorageService, get_storage_service


PDF_BYTES = b"%PDF-1.7\nportfolio-test\n%%EOF"


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self._next_id = 1

    def add(self, document) -> None:
        self.added.append(document)

    def flush(self) -> None:
        document = self.added[-1]
        document.id = self._next_id
        self._next_id += 1
        timestamp = datetime(2026, 10, 1, tzinfo=UTC)
        document.created_at = timestamp
        document.updated_at = timestamp

    def refresh(self, document) -> None:
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


@pytest.fixture
def client(tmp_path: Path):
    db = FakeSession()
    storage = StorageService(tmp_path)

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_storage_service] = lambda: storage

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_upload_pdf_returns_created_document(client: TestClient) -> None:
    response = client.post(
        "/api/documents",
        files={
            "file": (
                "manual.pdf",
                PDF_BYTES,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"] == 1
    assert payload["original_filename"] == "manual.pdf"
    assert payload["status"] == "uploaded"
    assert "filename" not in payload
    assert "file_path" not in payload


def test_upload_non_pdf_returns_bad_request(client: TestClient) -> None:
    response = client.post(
        "/api/documents",
        files={
            "file": (
                "manual.txt",
                b"plain text",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only PDF files are supported"


def test_upload_oversized_pdf_returns_413(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "max_upload_size_bytes", 8)

    response = client.post(
        "/api/documents",
        files={
            "file": (
                "manual.pdf",
                PDF_BYTES,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413
    assert "exceeds" in response.json()["detail"]


def test_upload_invalid_pdf_signature_returns_bad_request(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/documents",
        files={
            "file": (
                "manual.pdf",
                b"not-a-real-pdf",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded file is not a valid PDF"
