from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_embedding_provider_dependency,
    get_generation_provider_dependency,
)
from app.core.database import get_db
from app.main import app
from app.models.document_chunk import EMBEDDING_DIMENSION
from app.services.generation_service import GenerationProviderError


class FakeResult:
    def __init__(self, rows) -> None:
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, rows) -> None:
        self.rows = rows

    def execute(self, statement):
        return FakeResult(self.rows)


class FakeEmbeddingProvider:
    dimension = EMBEDDING_DIMENSION

    def embed_text(self, text: str) -> list[float]:
        return [0.1] * EMBEDDING_DIMENSION

    def embed_batch(self, texts):
        return [self.embed_text(text) for text in texts]


class FakeGenerationProvider:
    def __init__(
        self,
        answer: str = "The warranty period is 24 months.",
        error: Exception | None = None,
    ) -> None:
        self.answer = answer
        self.error = error

    def generate(self, messages):
        if self.error is not None:
            raise self.error
        return self.answer


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def make_client(rows, generation_provider=None) -> TestClient:
    app.dependency_overrides[get_db] = lambda: FakeSession(rows)
    app.dependency_overrides[get_embedding_provider_dependency] = (
        lambda: FakeEmbeddingProvider()
    )
    app.dependency_overrides[get_generation_provider_dependency] = (
        lambda: generation_provider or FakeGenerationProvider()
    )
    return TestClient(app)


def test_chat_returns_grounded_answer_and_deduplicated_sources() -> None:
    rows = [
        SimpleNamespace(
            chunk_id=1,
            document_id=3,
            document="manual.pdf",
            page_number=17,
            chunk_index=0,
            content="The warranty period is 24 months.",
            distance=0.05,
        ),
        SimpleNamespace(
            chunk_id=2,
            document_id=3,
            document="manual.pdf",
            page_number=17,
            chunk_index=1,
            content="Coverage begins on the purchase date.",
            distance=0.10,
        ),
        SimpleNamespace(
            chunk_id=3,
            document_id=4,
            document="policy.pdf",
            page_number=2,
            chunk_index=0,
            content="Proof of purchase is required.",
            distance=0.20,
        ),
    ]

    with make_client(rows) as client:
        response = client.post(
            "/api/chat",
            json={"question": "What is the warranty period?"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "The warranty period is 24 months.",
        "sources": [
            {
                "document_id": 3,
                "document": "manual.pdf",
                "page": 17,
            },
            {
                "document_id": 4,
                "document": "policy.pdf",
                "page": 2,
            },
        ],
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"question": ""},
        {"question": "   "},
    ],
)
def test_chat_rejects_empty_question(payload) -> None:
    with make_client([]) as client:
        response = client.post("/api/chat", json=payload)

    assert response.status_code == 422


def test_chat_generation_failure_returns_safe_503() -> None:
    provider = FakeGenerationProvider(
        error=GenerationProviderError("secret provider detail")
    )

    with make_client([], provider) as client:
        response = client.post(
            "/api/chat",
            json={"question": "Question"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Answer generation is temporarily unavailable"
    )
    assert "secret provider detail" not in response.text
