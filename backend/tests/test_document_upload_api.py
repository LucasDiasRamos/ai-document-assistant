from datetime import UTC, datetime
from pathlib import Path
import logging

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_embedding_provider_dependency
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.document_chunk import EMBEDDING_DIMENSION
from app.services.ingestion_service import DocumentIngestionError
from app.services.storage_service import StorageService, get_storage_service


def make_pdf_bytes() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Portfolio document content")
    data = document.tobytes()
    document.close()
    return data


PDF_BYTES = make_pdf_bytes()


class FakeEmbeddingProvider:
    dimension = EMBEDDING_DIMENSION

    def embed_text(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts):
        return [
            [float(index + 1)] * EMBEDDING_DIMENSION
            for index, _ in enumerate(texts)
        ]


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
    app.dependency_overrides[get_embedding_provider_dependency] = (
        lambda: FakeEmbeddingProvider()
    )

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
    assert payload["status"] == "processed"
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
    assert response.json() == {
        "detail": "Only PDF files are supported",
        "code": "unsupported_file",
    }


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
    assert response.json()["code"] == "upload_too_large"


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
    assert response.json() == {
        "detail": "Uploaded file is not a valid PDF",
        "code": "unsupported_file",
    }


def test_upload_request_limit_rejects_before_document_service(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "max_upload_size_bytes", 8)

    response = client.post(
        "/api/documents",
        files={
            "file": (
                "manual.pdf",
                b"%PDF-" + (b"x" * (70 * 1024)),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413
    assert response.json() == {
        "detail": "Upload request exceeds the allowed size",
        "code": "upload_too_large",
    }


def test_upload_filename_longer_than_database_limit_returns_400(
    client: TestClient,
) -> None:
    filename = f"{'a' * 252}.pdf"

    response = client.post(
        "/api/documents",
        files={
            "file": (
                filename,
                PDF_BYTES,
                "application/pdf",
            )
        },
    )

    assert len(filename) == 256
    assert response.status_code == 400
    assert response.json() == {
        "detail": "Filename must be at most 255 characters",
        "code": "validation_error",
    }


def test_upload_processing_failure_uses_safe_error_contract(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_processing(db, document, embedding_provider) -> None:
        document.error_message = "Document processing failed"
        raise DocumentIngestionError(
            "private implementation detail /tmp/secret.pdf"
        )

    monkeypatch.setattr(
        "app.api.routes.documents.process_document",
        fail_processing,
    )

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

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Document processing failed",
        "code": "processing_failed",
    }
    assert "/tmp/secret.pdf" not in response.text



def test_upload_logs_start_and_finish_without_filename_or_content(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(
        logging.INFO,
        logger="app.api.routes.documents",
    ):
        response = client.post(
            "/api/documents",
            files={
                "file": (
                    "sensitive-customer-file.pdf",
                    PDF_BYTES,
                    "application/pdf",
                )
            },
        )

    assert response.status_code == 201

    events = [
        getattr(record, "event", None)
        for record in caplog.records
        if record.name == "app.api.routes.documents"
    ]
    assert "document.upload.started" in events
    assert "document.upload.finished" in events

    finished = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "document.upload.finished"
    )
    assert finished.document_id == 1
    assert finished.status == "processed"
    assert "sensitive-customer-file.pdf" not in caplog.text
    assert "Portfolio document content" not in caplog.text


def test_rejected_upload_still_logs_finished_event(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(
        logging.INFO,
        logger="app.api.routes.documents",
    ):
        response = client.post(
            "/api/documents",
            files={
                "file": (
                    "not-a-pdf.txt",
                    b"private-content",
                    "text/plain",
                )
            },
        )

    assert response.status_code == 400

    finished = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "document.upload.finished"
    )
    assert finished.document_id is None
    assert finished.status == "rejected"
    assert "not-a-pdf.txt" not in caplog.text
    assert "private-content" not in caplog.text
