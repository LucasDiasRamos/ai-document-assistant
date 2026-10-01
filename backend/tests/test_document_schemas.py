from datetime import UTC, datetime
from types import SimpleNamespace

from app.models.document import DocumentStatus
from app.schemas.document import (
    APIError,
    DocumentListResponse,
    DocumentProcessingStatus,
    DocumentSummary,
)


def make_document() -> SimpleNamespace:
    timestamp = datetime(2026, 10, 1, tzinfo=UTC)
    return SimpleNamespace(
        id=1,
        filename="internal-uuid.pdf",
        original_filename="manual.pdf",
        file_path="/private/storage/internal-uuid.pdf",
        status=DocumentStatus.PROCESSED,
        error_message=None,
        created_at=timestamp,
        updated_at=timestamp,
    )


def test_document_summary_omits_internal_storage_fields() -> None:
    summary = DocumentSummary.model_validate(make_document())
    payload = summary.model_dump()

    assert payload["original_filename"] == "manual.pdf"
    assert payload["status"] == DocumentStatus.PROCESSED
    assert "filename" not in payload
    assert "file_path" not in payload


def test_document_list_response_has_stable_shape() -> None:
    summary = DocumentSummary.model_validate(make_document())
    response = DocumentListResponse(documents=[summary], total=1)

    assert response.total == 1
    assert len(response.documents) == 1


def test_processing_status_accepts_known_status() -> None:
    status = DocumentProcessingStatus(
        id=1,
        status=DocumentStatus.PROCESSING,
    )

    assert status.status == DocumentStatus.PROCESSING


def test_api_error_supports_optional_code() -> None:
    error = APIError(detail="Document not found", code="document_not_found")

    assert error.model_dump() == {
        "detail": "Document not found",
        "code": "document_not_found",
    }
