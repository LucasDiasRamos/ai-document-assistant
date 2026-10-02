from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.document import Document, DocumentStatus


def make_document(
    document_id: int,
    *,
    original_filename: str,
    status: DocumentStatus = DocumentStatus.PROCESSED,
    error_message: str | None = None,
) -> Document:
    timestamp = datetime(2026, 10, 1, document_id, tzinfo=UTC)

    return Document(
        id=document_id,
        filename=f"internal-{document_id}.pdf",
        original_filename=original_filename,
        file_path=f"/private/storage/internal-{document_id}.pdf",
        status=status,
        error_message=error_message,
        created_at=timestamp,
        updated_at=timestamp,
    )


class FakeScalarResult:
    def __init__(self, documents: list[Document]) -> None:
        self.documents = documents

    def all(self) -> list[Document]:
        return self.documents


class FakeSession:
    def __init__(self, documents: list[Document]) -> None:
        self.documents = documents

    def scalars(self, statement) -> FakeScalarResult:
        return FakeScalarResult(self.documents)

    def scalar(self, statement) -> int:
        return len(self.documents)

    def get(self, model, document_id: int) -> Document | None:
        return next(
            (
                document
                for document in self.documents
                if document.id == document_id
            ),
            None,
        )


def make_client(documents: list[Document]) -> TestClient:
    app.dependency_overrides[get_db] = lambda: FakeSession(documents)
    return TestClient(app)


def test_list_documents_returns_empty_collection() -> None:
    with make_client([]) as client:
        response = client.get("/api/documents")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "documents": [],
        "total": 0,
    }


def test_list_documents_returns_public_metadata_only() -> None:
    documents = [
        make_document(2, original_filename="second.pdf"),
        make_document(
            1,
            original_filename="first.pdf",
            status=DocumentStatus.FAILED,
            error_message="PDF text extraction failed",
        ),
    ]

    with make_client(documents) as client:
        response = client.get("/api/documents")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert [item["id"] for item in payload["documents"]] == [2, 1]
    assert payload["documents"][1]["error_message"] == (
        "PDF text extraction failed"
    )

    for item in payload["documents"]:
        assert "filename" not in item
        assert "file_path" not in item


def test_document_list_limit_is_bounded_by_api_contract() -> None:
    with make_client([]) as client:
        response = client.get("/api/documents?limit=101")

    app.dependency_overrides.clear()

    assert response.status_code == 422


def test_get_document_returns_public_detail() -> None:
    document = make_document(7, original_filename="manual.pdf")

    with make_client([document]) as client:
        response = client.get("/api/documents/7")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 7
    assert payload["original_filename"] == "manual.pdf"
    assert payload["status"] == "processed"
    assert "filename" not in payload
    assert "file_path" not in payload


def test_get_unknown_document_returns_404() -> None:
    with make_client([]) as client:
        response = client.get("/api/documents/999")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()
