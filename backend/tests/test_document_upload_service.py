from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.core.config import settings
from app.models.document import DocumentStatus
from app.services.document_service import (
    DocumentCleanupError,
    DocumentTooLargeError,
    EmptyDocumentError,
    InvalidPdfSignatureError,
    UnsupportedDocumentTypeError,
    create_uploaded_document,
)
from app.services.storage_service import StorageService


PDF_BYTES = b"%PDF-1.7\nportfolio-test\n%%EOF"


class FakeSession:
    def __init__(self, *, fail_flush: bool = False) -> None:
        self.fail_flush = fail_flush
        self.added = []
        self.committed = False
        self.rolled_back = False
        self._next_id = 1

    def add(self, document) -> None:
        self.added.append(document)

    def flush(self) -> None:
        if self.fail_flush:
            raise RuntimeError("database failure")

        document = self.added[-1]
        document.id = self._next_id
        self._next_id += 1
        timestamp = datetime(2026, 10, 1, tzinfo=UTC)
        document.created_at = timestamp
        document.updated_at = timestamp

    def refresh(self, document) -> None:
        return None

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


def make_upload(
    data: bytes,
    *,
    filename: str = "manual.pdf",
    content_type: str = "application/pdf",
) -> UploadFile:
    return UploadFile(
        file=BytesIO(data),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def test_valid_pdf_is_stored_and_document_is_persisted(tmp_path: Path) -> None:
    storage = StorageService(tmp_path)
    db = FakeSession()

    document = create_uploaded_document(
        db,
        make_upload(PDF_BYTES),
        storage=storage,
    )

    assert document.id == 1
    assert document.original_filename == "manual.pdf"
    assert document.filename.endswith(".pdf")
    assert document.filename != document.original_filename
    assert document.status == DocumentStatus.UPLOADED
    assert Path(document.file_path).exists()
    assert db.committed is True
    assert db.rolled_back is False


def test_duplicate_original_filename_is_allowed(tmp_path: Path) -> None:
    storage = StorageService(tmp_path)
    db = FakeSession()

    first = create_uploaded_document(
        db,
        make_upload(PDF_BYTES),
        storage=storage,
    )
    second = create_uploaded_document(
        db,
        make_upload(PDF_BYTES),
        storage=storage,
    )

    assert first.original_filename == second.original_filename
    assert first.filename != second.filename
    assert Path(first.file_path).exists()
    assert Path(second.file_path).exists()


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("manual.txt", "application/pdf"),
        ("manual.pdf", "text/plain"),
        ("", "application/pdf"),
    ],
)
def test_invalid_file_type_is_rejected(
    tmp_path: Path,
    filename: str,
    content_type: str,
) -> None:
    storage = StorageService(tmp_path)
    db = FakeSession()

    with pytest.raises(UnsupportedDocumentTypeError):
        create_uploaded_document(
            db,
            make_upload(
                PDF_BYTES,
                filename=filename,
                content_type=content_type,
            ),
            storage=storage,
        )

    assert list(tmp_path.iterdir()) == []
    assert db.added == []


def test_empty_pdf_is_rejected(tmp_path: Path) -> None:
    storage = StorageService(tmp_path)
    db = FakeSession()

    with pytest.raises(EmptyDocumentError):
        create_uploaded_document(
            db,
            make_upload(b""),
            storage=storage,
        )

    assert db.added == []


def test_oversized_pdf_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = StorageService(tmp_path)
    db = FakeSession()
    monkeypatch.setattr(settings, "max_upload_size_bytes", 8)

    with pytest.raises(DocumentTooLargeError):
        create_uploaded_document(
            db,
            make_upload(PDF_BYTES),
            storage=storage,
        )

    assert db.added == []


def test_invalid_pdf_signature_is_rejected(tmp_path: Path) -> None:
    storage = StorageService(tmp_path)
    db = FakeSession()

    with pytest.raises(InvalidPdfSignatureError):
        create_uploaded_document(
            db,
            make_upload(b"not-a-pdf"),
            storage=storage,
        )

    assert db.added == []


def test_database_failure_rolls_back_and_removes_stored_file(
    tmp_path: Path,
) -> None:
    storage = StorageService(tmp_path)
    db = FakeSession(fail_flush=True)

    with pytest.raises(RuntimeError, match="database failure"):
        create_uploaded_document(
            db,
            make_upload(PDF_BYTES),
            storage=storage,
        )

    assert db.rolled_back is True
    assert list(tmp_path.iterdir()) == []


class FailingDeleteStorage(StorageService):
    def delete(self, path):
        raise OSError("cleanup failure")


def test_database_and_cleanup_failure_is_not_silent(tmp_path: Path) -> None:
    storage = FailingDeleteStorage(tmp_path)
    db = FakeSession(fail_flush=True)

    with pytest.raises(DocumentCleanupError, match="cleanup also failed"):
        create_uploaded_document(
            db,
            make_upload(PDF_BYTES),
            storage=storage,
        )

    assert db.rolled_back is True
    assert len(list(tmp_path.iterdir())) == 1
