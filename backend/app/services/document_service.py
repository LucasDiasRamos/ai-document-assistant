from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document, DocumentStatus
from app.services.storage_service import StorageService, storage_service


class DocumentUploadValidationError(ValueError):
    pass


class UnsupportedDocumentTypeError(DocumentUploadValidationError):
    pass


class EmptyDocumentError(DocumentUploadValidationError):
    pass


class DocumentTooLargeError(DocumentUploadValidationError):
    pass


class InvalidPdfSignatureError(DocumentUploadValidationError):
    pass


class DocumentCleanupError(RuntimeError):
    pass


def create_uploaded_document(
    db: Session,
    upload: UploadFile,
    *,
    storage: StorageService = storage_service,
) -> Document:
    original_filename = _validate_upload(upload)

    stored = storage.save(
        upload.file,
        original_filename=original_filename,
        suffix=".pdf",
    )

    document = Document(
        filename=stored.filename,
        original_filename=stored.original_filename,
        file_path=str(stored.path),
        status=DocumentStatus.UPLOADED,
    )

    try:
        db.add(document)
        db.flush()
        db.refresh(document)
        db.commit()
    except Exception as persistence_error:
        db.rollback()
        try:
            storage.delete(stored.path)
        except Exception as cleanup_error:
            raise DocumentCleanupError(
                "Document persistence failed and stored-file cleanup also failed"
            ) from cleanup_error
        raise persistence_error

    return document


def _validate_upload(upload: UploadFile) -> str:
    original_filename = (upload.filename or "").strip()

    if not original_filename:
        raise UnsupportedDocumentTypeError("A filename is required")

    if Path(original_filename).suffix.lower() != ".pdf":
        raise UnsupportedDocumentTypeError("Only PDF files are supported")

    if upload.content_type != "application/pdf":
        raise UnsupportedDocumentTypeError("Content-Type must be application/pdf")

    stream = upload.file
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)

    if size == 0:
        raise EmptyDocumentError("Uploaded PDF is empty")

    if size > settings.max_upload_size_bytes:
        raise DocumentTooLargeError(
            f"Uploaded PDF exceeds the {settings.max_upload_size_bytes}-byte limit"
        )

    signature = stream.read(5)
    stream.seek(0)

    if signature != b"%PDF-":
        raise InvalidPdfSignatureError("Uploaded file is not a valid PDF")

    return original_filename
