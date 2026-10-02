from types import SimpleNamespace

from app.models.document_chunk import EMBEDDING_DIMENSION
from app.services.generation_service import GenerationMessage
from app.services.rag_service import answer_question


class FakeResult:
    def __init__(self, rows) -> None:
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, rows) -> None:
        self.rows = rows
        self.rollback_count = 0

    def execute(self, statement):
        return FakeResult(self.rows)

    def rollback(self) -> None:
        self.rollback_count += 1


class FakeEmbeddingProvider:
    dimension = EMBEDDING_DIMENSION

    def embed_text(self, text: str) -> list[float]:
        return [0.1] * EMBEDDING_DIMENSION

    def embed_batch(self, texts):
        return [self.embed_text(text) for text in texts]


class FakeGenerationProvider:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.messages = None

    def generate(self, messages):
        self.messages = list(messages)
        return self.answer


def test_answer_question_composes_retrieval_prompt_and_generation() -> None:
    db = FakeSession(
        [
            SimpleNamespace(
                chunk_id=1,
                document_id=10,
                document="manual.pdf",
                page_number=7,
                chunk_index=0,
                content="The warranty period is 24 months.",
                distance=0.05,
            ),
            SimpleNamespace(
                chunk_id=2,
                document_id=10,
                document="manual.pdf",
                page_number=7,
                chunk_index=1,
                content="Coverage starts on the purchase date.",
                distance=0.10,
            ),
            SimpleNamespace(
                chunk_id=3,
                document_id=11,
                document="policy.pdf",
                page_number=2,
                chunk_index=0,
                content="Proof of purchase is required.",
                distance=0.20,
            ),
        ]
    )
    generation = FakeGenerationProvider("The warranty is 24 months.")

    result = answer_question(
        db,
        "What is the warranty period?",
        FakeEmbeddingProvider(),
        generation,
    )

    assert result.answer == "The warranty is 24 months."
    assert db.rollback_count == 1
    assert [
        (source.document_id, source.document, source.page_number)
        for source in result.sources
    ] == [
        (10, "manual.pdf", 7),
        (11, "policy.pdf", 2),
    ]

    assert generation.messages is not None
    assert generation.messages[0].role == "developer"
    assert generation.messages[1].role == "user"
    assert "Answer only from the supplied DOCUMENT CONTEXT" in (
        generation.messages[0].content
    )
    assert "What is the warranty period?" in generation.messages[1].content
    assert "The warranty period is 24 months." in (
        generation.messages[1].content
    )
    assert "[Source: manual.pdf | Page: 7]" in generation.messages[1].content


def test_empty_context_short_circuits_generation() -> None:
    db = FakeSession([])
    generation = FakeGenerationProvider("fabricated answer")

    result = answer_question(
        db,
        "Unknown question",
        FakeEmbeddingProvider(),
        generation,
    )

    assert result.answer == (
        "I could not find that information in the uploaded documents."
    )
    assert result.sources == ()
    assert generation.messages is None
    assert db.rollback_count == 1


def test_generation_receives_exactly_developer_and_user_messages() -> None:
    db = FakeSession(
        [
            SimpleNamespace(
                chunk_id=1,
                document_id=10,
                document="manual.pdf",
                page_number=7,
                chunk_index=0,
                content="Known context.",
                distance=0.05,
            )
        ]
    )
    generation = FakeGenerationProvider("Grounded answer")

    answer_question(
        db,
        "Known question",
        FakeEmbeddingProvider(),
        generation,
    )

    assert generation.messages == [
        GenerationMessage(
            role="developer",
            content=generation.messages[0].content,
        ),
        GenerationMessage(
            role="user",
            content=generation.messages[1].content,
        ),
    ]
    assert len(generation.messages) == 2
    assert db.rollback_count == 1



def test_database_read_transaction_is_released_before_generation() -> None:
    db = FakeSession(
        [
            SimpleNamespace(
                chunk_id=1,
                document_id=10,
                document="manual.pdf",
                page_number=7,
                chunk_index=0,
                content="Known context.",
                distance=0.05,
            )
        ]
    )

    class TransactionAwareGenerationProvider:
        def generate(self, messages):
            assert db.rollback_count == 1
            return "Grounded answer"

    result = answer_question(
        db,
        "Known question",
        FakeEmbeddingProvider(),
        TransactionAwareGenerationProvider(),
    )

    assert result.answer == "Grounded answer"
