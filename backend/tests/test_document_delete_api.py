from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.document import Document, DocumentStatus
from app.services.storage_service import StorageService, get_storage_service


def make_document(path: Path) -> Document:
    timestamp = datetime(2026, 10, 1, tzinfo=UTC)

    return Document(
        id=7,
        filename=path.name,
        original_filename="manual.pdf",
        file_path=str(path),
        status=DocumentStatus.PROCESSED,
        created_at=timestamp,
        updated_at=timestamp,
    )


class FakeSession:
    def __init__(self, document: Document | None) -> None:
        self.document = document
        self.deleted = []
        self.committed = False
        self.rolled_back = False

    def get(self, model, document_id: int):
        if self.document is not None and self.document.id == document_id:
            return self.document
        return None

    def delete(self, value) -> None:
        self.deleted.append(value)

    def commit(self) -> None:
        self.committed = True
        self.document = None

    def rollback(self) -> None:
        self.rolled_back = True


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_delete_document_returns_204_and_removes_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "stored.pdf"
    path.write_bytes(b"%PDF-test")
    document = make_document(path)
    db = FakeSession(document)
    storage = StorageService(tmp_path)

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_storage_service] = lambda: storage

    with TestClient(app) as client:
        response = client.delete("/api/documents/7")

    assert response.status_code == 204
    assert response.content == b""
    assert db.deleted == [document]
    assert db.committed is True
    assert not path.exists()


def test_delete_unknown_document_returns_404(tmp_path: Path) -> None:
    db = FakeSession(None)
    storage = StorageService(tmp_path)

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_storage_service] = lambda: storage

    with TestClient(app) as client:
        response = client.delete("/api/documents/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"
    assert db.deleted == []


def test_delete_succeeds_when_file_is_already_missing(
    tmp_path: Path,
) -> None:
    path = tmp_path / "missing.pdf"
    document = make_document(path)
    db = FakeSession(document)
    storage = StorageService(tmp_path)

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_storage_service] = lambda: storage

    with TestClient(app) as client:
        response = client.delete("/api/documents/7")

    assert response.status_code == 204
    assert db.committed is True
