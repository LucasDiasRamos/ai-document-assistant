import logging

import pytest

from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk, EMBEDDING_DIMENSION
from app.services.chunk_service import TextChunk
from app.services.embedding_service import EmbeddingProviderError
from app.services.ingestion_service import (
    InvalidEmbeddingBatchError,
    NoExtractableTextError,
    process_document,
)
from app.services.pdf_service import ExtractedPage, InvalidPdfError


def make_document() -> Document:
    document = Document(
        id=1,
        filename="stored.pdf",
        original_filename="manual.pdf",
        file_path="/tmp/stored.pdf",
        status=DocumentStatus.UPLOADED,
    )
    document.chunks = []
    return document


def embedding(value: float) -> list[float]:
    return [value] * EMBEDDING_DIMENSION


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.commits = []
        self.rollback_count = 0
        self.flush_chunk_counts = []

    def add(self, value) -> None:
        self.added.append(value)

    def commit(self) -> None:
        document = self.added[-1]
        self.commits.append(
            {
                "status": document.status,
                "error_message": document.error_message,
                "chunk_count": len(document.chunks),
            }
        )

    def refresh(self, value) -> None:
        return None

    def flush(self) -> None:
        document = self.added[-1]
        self.flush_chunk_counts.append(len(document.chunks))

    def rollback(self) -> None:
        self.rollback_count += 1


class FakeEmbeddingProvider:
    dimension = EMBEDDING_DIMENSION

    def __init__(
        self,
        *,
        vectors: list[list[float]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.vectors = vectors or []
        self.error = error
        self.inputs = []

    def embed_text(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts):
        self.inputs.append(list(texts))
        if self.error is not None:
            raise self.error
        return self.vectors


def extracted_pages(_: str) -> list[ExtractedPage]:
    return [
        ExtractedPage(page_number=1, text="first page"),
        ExtractedPage(page_number=2, text="second page"),
    ]


def prepared_chunks(_pages) -> list[TextChunk]:
    return [
        TextChunk(page_number=1, chunk_index=0, content="first chunk"),
        TextChunk(page_number=2, chunk_index=1, content="second chunk"),
    ]


def test_happy_path_persists_chunks_and_processed_status() -> None:
    db = FakeSession()
    document = make_document()
    provider = FakeEmbeddingProvider(
        vectors=[embedding(0.1), embedding(0.2)]
    )

    result = process_document(
        db,
        document,
        provider,
        page_extractor=extracted_pages,
        page_chunker=prepared_chunks,
    )

    assert result is document
    assert document.status == DocumentStatus.PROCESSED
    assert document.error_message is None
    assert [
        (
            chunk.page_number,
            chunk.chunk_index,
            chunk.content,
            chunk.embedding[0],
        )
        for chunk in document.chunks
    ] == [
        (1, 0, "first chunk", 0.1),
        (2, 1, "second chunk", 0.2),
    ]
    assert provider.inputs == [["first chunk", "second chunk"]]
    assert db.commits == [
        {
            "status": DocumentStatus.PROCESSING,
            "error_message": None,
            "chunk_count": 0,
        },
        {
            "status": DocumentStatus.PROCESSED,
            "error_message": None,
            "chunk_count": 2,
        },
    ]
    assert db.rollback_count == 0


def test_extraction_failure_marks_document_failed() -> None:
    db = FakeSession()
    document = make_document()
    provider = FakeEmbeddingProvider()

    def failing_extractor(_: str):
        raise InvalidPdfError("technical path should not be persisted")

    with pytest.raises(InvalidPdfError):
        process_document(
            db,
            document,
            provider,
            page_extractor=failing_extractor,
            page_chunker=prepared_chunks,
        )

    assert document.status == DocumentStatus.FAILED
    assert document.error_message == "PDF text extraction failed"
    assert document.chunks == []
    assert provider.inputs == []
    assert db.rollback_count == 1
    assert db.commits[-1]["status"] == DocumentStatus.FAILED


def test_embedding_failure_marks_document_failed_without_partial_chunks() -> None:
    db = FakeSession()
    document = make_document()
    provider = FakeEmbeddingProvider(
        error=EmbeddingProviderError("provider secret detail")
    )

    with pytest.raises(EmbeddingProviderError):
        process_document(
            db,
            document,
            provider,
            page_extractor=extracted_pages,
            page_chunker=prepared_chunks,
        )

    assert document.status == DocumentStatus.FAILED
    assert document.error_message == "Embedding generation failed"
    assert document.chunks == []
    assert db.rollback_count == 1


def test_no_extractable_text_marks_document_failed() -> None:
    db = FakeSession()
    document = make_document()
    provider = FakeEmbeddingProvider()

    with pytest.raises(NoExtractableTextError):
        process_document(
            db,
            document,
            provider,
            page_extractor=extracted_pages,
            page_chunker=lambda _: [],
        )

    assert document.status == DocumentStatus.FAILED
    assert document.error_message == "No extractable text was found in the PDF"
    assert provider.inputs == []


def test_embedding_count_mismatch_is_rejected_before_persistence() -> None:
    db = FakeSession()
    document = make_document()
    provider = FakeEmbeddingProvider(vectors=[embedding(0.1)])

    with pytest.raises(
        InvalidEmbeddingBatchError,
        match="different number of vectors",
    ):
        process_document(
            db,
            document,
            provider,
            page_extractor=extracted_pages,
            page_chunker=prepared_chunks,
        )

    assert document.status == DocumentStatus.FAILED
    assert document.error_message == (
        "Embedding generation returned invalid data"
    )
    assert document.chunks == []


def test_embedding_dimension_mismatch_is_rejected_before_persistence() -> None:
    db = FakeSession()
    document = make_document()
    provider = FakeEmbeddingProvider(
        vectors=[
            [0.1] * (EMBEDDING_DIMENSION - 1),
            embedding(0.2),
        ]
    )

    with pytest.raises(
        InvalidEmbeddingBatchError,
        match="dimension",
    ):
        process_document(
            db,
            document,
            provider,
            page_extractor=extracted_pages,
            page_chunker=prepared_chunks,
        )

    assert document.status == DocumentStatus.FAILED
    assert document.chunks == []


def test_successful_reprocessing_replaces_existing_chunks() -> None:
    db = FakeSession()
    document = make_document()
    document.chunks = [
        DocumentChunk(
            content="old",
            page_number=1,
            chunk_index=0,
            embedding=embedding(0.9),
        )
    ]
    provider = FakeEmbeddingProvider(
        vectors=[embedding(0.1), embedding(0.2)]
    )

    process_document(
        db,
        document,
        provider,
        page_extractor=extracted_pages,
        page_chunker=prepared_chunks,
    )

    assert [chunk.content for chunk in document.chunks] == [
        "first chunk",
        "second chunk",
    ]
    assert db.flush_chunk_counts == [0]


def test_failed_reprocessing_keeps_existing_chunks() -> None:
    db = FakeSession()
    document = make_document()
    old_chunk = DocumentChunk(
        content="previous searchable content",
        page_number=1,
        chunk_index=0,
        embedding=embedding(0.9),
    )
    document.chunks = [old_chunk]
    provider = FakeEmbeddingProvider(
        error=EmbeddingProviderError("temporary provider failure")
    )

    with pytest.raises(EmbeddingProviderError):
        process_document(
            db,
            document,
            provider,
            page_extractor=extracted_pages,
            page_chunker=prepared_chunks,
        )

    assert document.status == DocumentStatus.FAILED
    assert document.chunks == [old_chunk]


def test_ingestion_failure_logs_safe_technical_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    db = FakeSession()
    document = make_document()
    provider = FakeEmbeddingProvider(
        error=EmbeddingProviderError("provider-secret-detail")
    )

    with caplog.at_level(
        logging.ERROR,
        logger="app.services.ingestion_service",
    ):
        with pytest.raises(EmbeddingProviderError):
            process_document(
                db,
                document,
                provider,
                page_extractor=extracted_pages,
                page_chunker=prepared_chunks,
            )

    record = next(
        record
        for record in caplog.records
        if record.message == "Document ingestion failed"
    )
    assert record.document_id == document.id
    assert "EmbeddingProviderError" in record.error_types
    assert "provider-secret-detail" not in caplog.text
