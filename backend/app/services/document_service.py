from __future__ import annotations

from pathlib import Path
import logging

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import (
    DOCUMENT_FILENAME_MAX_LENGTH,
    Document,
    DocumentStatus,
)
from app.services.storage_service import StorageService, storage_service


logger = logging.getLogger(__name__)


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


class DocumentDeleteError(RuntimeError):
    pass


class DocumentFileCleanupError(DocumentDeleteError):
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
        raise

    return document


def _validate_upload(upload: UploadFile) -> str:
    original_filename = (upload.filename or "").strip()

    if not original_filename:
        raise UnsupportedDocumentTypeError("A filename is required")

    if len(original_filename) > DOCUMENT_FILENAME_MAX_LENGTH:
        raise DocumentUploadValidationError(
            f"Filename must be at most {DOCUMENT_FILENAME_MAX_LENGTH} characters"
        )

    # Never persist path traversal or control characters from a client filename.
    if (
        "/" in original_filename
        or chr(92) in original_filename
        or any(ord(char) < 32 or ord(char) == 127 for char in original_filename)
    ):
        raise DocumentUploadValidationError("Filename contains unsafe characters")

    if Path(original_filename).suffix.lower() != ".pdf":
        raise UnsupportedDocumentTypeError("Only PDF files are supported")

    content_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
    if content_type != "application/pdf":
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



DEFAULT_DOCUMENT_LIST_LIMIT = 50
MAX_DOCUMENT_LIST_LIMIT = 100


def list_documents(
    db: Session,
    *,
    limit: int = DEFAULT_DOCUMENT_LIST_LIMIT,
) -> tuple[list[Document], int]:
    if limit < 1 or limit > MAX_DOCUMENT_LIST_LIMIT:
        raise ValueError(
            f"limit must be between 1 and {MAX_DOCUMENT_LIST_LIMIT}"
        )

    documents = list(
        db.scalars(
            select(Document)
            .order_by(Document.created_at.desc(), Document.id.desc())
            .limit(limit)
        ).all()
    )
    total = db.scalar(select(func.count(Document.id)))

    return documents, int(total or 0)


def get_document_by_id(
    db: Session,
    document_id: int,
) -> Document | None:
    return db.get(Document, document_id)



def delete_document(
    db: Session,
    document: Document,
    *,
    storage: StorageService = storage_service,
) -> None:
    document_id = document.id
    stored_path = document.file_path

    try:
        db.delete(document)
        db.commit()
    except Exception:
        db.rollback()
        raise

    try:
        deleted = storage.delete(stored_path)
    except Exception as exc:
        logger.error(
            "Document file cleanup failed document_id=%s error_type=%s",
            document_id,
            type(exc).__name__,
        )
        raise DocumentFileCleanupError(
            "Document metadata was deleted but stored file cleanup failed"
        ) from exc

    if not deleted:
        logger.info(
            "Document file already absent during delete document_id=%s",
            document_id,
        )
