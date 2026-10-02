from __future__ import annotations

from collections.abc import Callable, Sequence
import logging

from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk, EMBEDDING_DIMENSION
from app.services.chunk_service import TextChunk, chunk_pages
from app.services.embedding_service import EmbeddingError, EmbeddingProvider
from app.services.pdf_service import (
    ExtractedPage,
    PdfExtractionError,
    extract_pdf_pages,
)


logger = logging.getLogger(__name__)


class DocumentIngestionError(RuntimeError):
    """Base error for document ingestion failures."""


class NoExtractableTextError(DocumentIngestionError):
    pass


class InvalidEmbeddingBatchError(DocumentIngestionError):
    pass


class DocumentFailureStateError(DocumentIngestionError):
    pass


PageExtractor = Callable[[str], list[ExtractedPage]]
PageChunker = Callable[[Sequence[ExtractedPage]], list[TextChunk]]


def process_document(
    db: Session,
    document: Document,
    embedding_provider: EmbeddingProvider,
    *,
    page_extractor: PageExtractor = extract_pdf_pages,
    page_chunker: PageChunker = chunk_pages,
) -> Document:
    try:
        _mark_processing(db, document)
        pages = page_extractor(document.file_path)
        chunks = page_chunker(pages)

        if not chunks:
            raise NoExtractableTextError(
                "No extractable text was found in the document"
            )

        embeddings = embedding_provider.embed_batch(
            [chunk.content for chunk in chunks]
        )
        _validate_embeddings(chunks, embeddings)

        persisted_chunks = [
            DocumentChunk(
                content=chunk.content,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                embedding=embedding,
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]

        if document.chunks:
            document.chunks.clear()
            db.flush()

        document.chunks.extend(persisted_chunks)
        document.status = DocumentStatus.PROCESSED
        document.error_message = None
        db.add(document)
        db.commit()
        db.refresh(document)
    except Exception as exc:
        error_types = _error_type_chain(exc)
        logger.error(
            "Document ingestion failed document_id=%s error_types=%s",
            document.id,
            error_types,
            extra={
                "document_id": document.id,
                "error_types": error_types,
            },
        )
        db.rollback()
        _mark_failed(db, document, exc)
        raise

    return document


def _mark_processing(db: Session, document: Document) -> None:
    document.status = DocumentStatus.PROCESSING
    document.error_message = None
    db.add(document)
    db.commit()
    db.refresh(document)


def _mark_failed(
    db: Session,
    document: Document,
    error: Exception,
) -> None:
    document.status = DocumentStatus.FAILED
    document.error_message = _safe_failure_message(error)
    db.add(document)

    try:
        db.commit()
        db.refresh(document)
    except Exception as state_error:
        db.rollback()
        raise DocumentFailureStateError(
            "Document processing failed and the failed state could not be persisted"
        ) from state_error


def _validate_embeddings(
    chunks: Sequence[TextChunk],
    embeddings: Sequence[Sequence[float]],
) -> None:
    if len(embeddings) != len(chunks):
        raise InvalidEmbeddingBatchError(
            "Embedding provider returned a different number of vectors than chunks"
        )

    for embedding in embeddings:
        if len(embedding) != EMBEDDING_DIMENSION:
            raise InvalidEmbeddingBatchError(
                "Embedding vector dimension does not match the database schema"
            )


def _safe_failure_message(error: Exception) -> str:
    if isinstance(error, NoExtractableTextError):
        return "No extractable text was found in the PDF"

    if isinstance(error, PdfExtractionError):
        return "PDF text extraction failed"

    if isinstance(error, EmbeddingError):
        return "Embedding generation failed"

    if isinstance(error, InvalidEmbeddingBatchError):
        return "Embedding generation returned invalid data"

    return "Document processing failed"


def _error_type_chain(error: Exception) -> str:
    error_types: list[str] = []
    current: BaseException | None = error

    while current is not None and len(error_types) < 5:
        error_types.append(type(current).__name__)
        current = current.__cause__ or current.__context__

    return " <- ".join(error_types)
