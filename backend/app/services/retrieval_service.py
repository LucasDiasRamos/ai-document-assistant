from __future__ import annotations

from dataclasses import dataclass
import logging
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.observability import elapsed_ms, log_event
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk, EMBEDDING_DIMENSION
from app.services.embedding_service import EmbeddingProvider


MAX_RETRIEVAL_TOP_K = 20
logger = logging.getLogger(__name__)


class RetrievalError(RuntimeError):
    """Base error for retrieval failures."""


class RetrievalInputError(RetrievalError):
    pass


class RetrievalEmbeddingDimensionError(RetrievalError):
    pass


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: int
    document_id: int
    document: str
    page_number: int
    chunk_index: int
    content: str
    distance: float

    @property
    def similarity(self) -> float:
        return 1.0 - self.distance


def retrieve_relevant_chunks(
    db: Session,
    question: str,
    embedding_provider: EmbeddingProvider,
    *,
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    started_at = perf_counter()
    normalized_question = question.strip()
    if not normalized_question:
        raise RetrievalInputError("Question must not be empty")

    limit = top_k if top_k is not None else settings.retrieval_top_k
    if limit < 1 or limit > MAX_RETRIEVAL_TOP_K:
        raise RetrievalInputError(
            f"top_k must be between 1 and {MAX_RETRIEVAL_TOP_K}"
        )

    question_embedding = embedding_provider.embed_text(normalized_question)
    if len(question_embedding) != EMBEDDING_DIMENSION:
        raise RetrievalEmbeddingDimensionError(
            "Query embedding dimension does not match the database schema: "
            f"expected {EMBEDDING_DIMENSION}, "
            f"received {len(question_embedding)}"
        )

    distance = DocumentChunk.embedding.cosine_distance(
        question_embedding
    ).label("distance")

    statement = (
        select(
            DocumentChunk.id.label("chunk_id"),
            DocumentChunk.document_id,
            Document.original_filename.label("document"),
            DocumentChunk.page_number,
            DocumentChunk.chunk_index,
            DocumentChunk.content,
            distance,
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.status == DocumentStatus.PROCESSED)
        .order_by(distance.asc(), DocumentChunk.id.asc())
        .limit(limit)
    )

    rows = db.execute(statement).all()

    log_event(
        logger,
        logging.INFO,
        "retrieval.completed",
        result_count=len(rows),
        duration_ms=elapsed_ms(started_at),
    )

    return [
        RetrievedChunk(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            document=row.document,
            page_number=row.page_number,
            chunk_index=row.chunk_index,
            content=row.content,
            distance=float(row.distance),
        )
        for row in rows
    ]
