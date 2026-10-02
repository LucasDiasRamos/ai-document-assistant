from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk, EMBEDDING_DIMENSION
from app.services.retrieval_service import retrieve_relevant_chunks


def embedding(x: float, y: float) -> list[float]:
    return [x, y] + [0.0] * (EMBEDDING_DIMENSION - 2)


class StaticEmbeddingProvider:
    dimension = EMBEDDING_DIMENSION

    def __init__(self, value: list[float]) -> None:
        self.value = value

    def embed_text(self, text: str) -> list[float]:
        return self.value

    def embed_batch(self, texts):
        return [self.value for _ in texts]


def test_pgvector_cosine_ranking_limit_and_processed_filter() -> None:
    try:
        with engine.connect() as connection:
            connection.execute(select(1))
    except OperationalError:
        pytest.skip("PostgreSQL test database is not available")

    suffix = uuid4().hex
    db = Session(engine)

    try:
        processed = Document(
            filename=f"processed-{suffix}.pdf",
            original_filename="processed.pdf",
            file_path=f"/tmp/processed-{suffix}.pdf",
            status=DocumentStatus.PROCESSED,
        )
        failed = Document(
            filename=f"failed-{suffix}.pdf",
            original_filename="failed.pdf",
            file_path=f"/tmp/failed-{suffix}.pdf",
            status=DocumentStatus.FAILED,
        )
        db.add_all([processed, failed])
        db.flush()

        near = DocumentChunk(
            document_id=processed.id,
            content="nearest processed chunk",
            page_number=1,
            chunk_index=0,
            embedding=embedding(1.0, 0.0),
        )
        medium = DocumentChunk(
            document_id=processed.id,
            content="second processed chunk",
            page_number=2,
            chunk_index=1,
            embedding=embedding(0.8, 0.6),
        )
        far = DocumentChunk(
            document_id=processed.id,
            content="far processed chunk",
            page_number=3,
            chunk_index=2,
            embedding=embedding(0.0, 1.0),
        )
        excluded = DocumentChunk(
            document_id=failed.id,
            content="closer but failed document",
            page_number=1,
            chunk_index=0,
            embedding=embedding(1.0, 0.0),
        )
        db.add_all([near, medium, far, excluded])
        db.flush()

        results = retrieve_relevant_chunks(
            db,
            "known question",
            StaticEmbeddingProvider(embedding(1.0, 0.0)),
            top_k=2,
        )

        assert [result.content for result in results] == [
            "nearest processed chunk",
            "second processed chunk",
        ]
        assert all(
            result.document_id == processed.id
            for result in results
        )
        assert [result.distance for result in results] == pytest.approx(
            [0.0, 0.2]
        )
    finally:
        db.rollback()
        db.close()
