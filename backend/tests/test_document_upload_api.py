from datetime import UTC, datetime
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_embedding_provider_dependency
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.document_chunk import EMBEDDING_DIMENSION
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
    assert response.json()["detail"] == (
        "Upload request exceeds the allowed size"
    )


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
    assert response.json()["detail"] == (
        "Filename must be at most 255 characters"
    )
