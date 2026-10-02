from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from app.models.document_chunk import EMBEDDING_DIMENSION
from app.services.retrieval_service import (
    MAX_RETRIEVAL_TOP_K,
    RetrievalEmbeddingDimensionError,
    RetrievalInputError,
    retrieve_relevant_chunks,
)


def vector(value: float = 0.1) -> list[float]:
    return [value] * EMBEDDING_DIMENSION


class FakeEmbeddingProvider:
    dimension = EMBEDDING_DIMENSION

    def __init__(self) -> None:
        self.inputs = []

    def embed_text(self, text: str) -> list[float]:
        self.inputs.append(text)
        return vector()

    def embed_batch(self, texts):
        return [self.embed_text(text) for text in texts]


class FakeResult:
    def __init__(self, rows) -> None:
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, rows) -> None:
        self.rows = rows
        self.statement = None

    def execute(self, statement):
        self.statement = statement
        return FakeResult(self.rows)


def test_retrieval_maps_ranked_rows_with_citation_metadata() -> None:
    rows = [
        SimpleNamespace(
            chunk_id=11,
            document_id=3,
            document="manual.pdf",
            page_number=7,
            chunk_index=2,
            content="Relevant warranty text",
            distance=0.08,
        ),
        SimpleNamespace(
            chunk_id=12,
            document_id=4,
            document="policy.pdf",
            page_number=2,
            chunk_index=0,
            content="Secondary context",
            distance=0.22,
        ),
    ]
    db = FakeSession(rows)
    provider = FakeEmbeddingProvider()

    results = retrieve_relevant_chunks(
        db,
        "  What is the warranty period?  ",
        provider,
        top_k=2,
    )

    assert provider.inputs == ["What is the warranty period?"]
    assert [result.chunk_id for result in results] == [11, 12]
    assert results[0].document_id == 3
    assert results[0].document == "manual.pdf"
    assert results[0].page_number == 7
    assert results[0].chunk_index == 2
    assert results[0].content == "Relevant warranty text"
    assert results[0].distance == pytest.approx(0.08)
    assert results[0].similarity == pytest.approx(0.92)


def test_retrieval_query_uses_cosine_distance_processed_filter_and_limit() -> None:
    db = FakeSession([])
    provider = FakeEmbeddingProvider()

    retrieve_relevant_chunks(
        db,
        "known question",
        provider,
        top_k=3,
    )

    compiled = str(
        db.statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "<=>" in compiled
    assert "documents.status = 'processed'" in compiled
    assert "ORDER BY" in compiled
    assert "LIMIT 3" in compiled


def test_empty_question_is_rejected_before_embedding() -> None:
    db = FakeSession([])
    provider = FakeEmbeddingProvider()

    with pytest.raises(RetrievalInputError, match="must not be empty"):
        retrieve_relevant_chunks(
            db,
            "   ",
            provider,
        )

    assert provider.inputs == []
    assert db.statement is None


@pytest.mark.parametrize("top_k", [0, MAX_RETRIEVAL_TOP_K + 1])
def test_invalid_top_k_is_rejected_before_embedding(top_k: int) -> None:
    db = FakeSession([])
    provider = FakeEmbeddingProvider()

    with pytest.raises(RetrievalInputError, match="top_k must be between"):
        retrieve_relevant_chunks(
            db,
            "question",
            provider,
            top_k=top_k,
        )

    assert provider.inputs == []
    assert db.statement is None


def test_empty_retrieval_result_is_supported() -> None:
    db = FakeSession([])
    provider = FakeEmbeddingProvider()

    results = retrieve_relevant_chunks(
        db,
        "question",
        provider,
        top_k=5,
    )

    assert results == []


def test_wrong_query_embedding_dimension_is_rejected_before_sql() -> None:
    db = FakeSession([])
    provider = FakeEmbeddingProvider()
    provider.embed_text = lambda text: [0.1] * (EMBEDDING_DIMENSION - 1)

    with pytest.raises(
        RetrievalEmbeddingDimensionError,
        match="does not match the database schema",
    ):
        retrieve_relevant_chunks(
            db,
            "question",
            provider,
        )

    assert db.statement is None
