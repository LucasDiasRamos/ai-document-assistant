from __future__ import annotations

import json
import math
from pathlib import Path
import shutil
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import EMBEDDING_DIMENSION
from app.services.chunk_service import TextChunk, chunk_pages
from app.services.ingestion_service import process_document
from app.services.pdf_service import extract_pdf_pages
from app.services.retrieval_service import retrieve_relevant_chunks


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "rag_eval"
CASES_PATH = FIXTURE_ROOT / "cases.json"
EVALUATION_CASES = json.loads(
    CASES_PATH.read_text(encoding="utf-8")
)

CONCEPT_DIMENSIONS = {
    "remote": 0,
    "training": 1,
    "incident": 2,
    "warranty": 3,
    "battery": 4,
    "maintenance": 5,
}
UNSUPPORTED_DIMENSION = 100


class EvaluationEmbeddingProvider:
    dimension = EMBEDDING_DIMENSION

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIMENSION
        lowered = text.lower()
        matched = False

        for keyword, dimension in CONCEPT_DIMENSIONS.items():
            if keyword in lowered:
                vector[dimension] = 1.0
                matched = True

        if not matched:
            vector[UNSUPPORTED_DIMENSION] = 1.0

        return vector

    def embed_batch(self, texts) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]


@pytest.fixture(scope="module")
def cases() -> dict:
    return EVALUATION_CASES


@pytest.fixture(scope="module")
def corpus_chunks(cases: dict) -> list[tuple[str, TextChunk]]:
    chunks: list[tuple[str, TextChunk]] = []

    for document in cases["documents"]:
        path = FIXTURE_ROOT / document["file"]
        pages = extract_pdf_pages(path)

        assert len(pages) == 3

        chunks.extend(
            (document["original_filename"], chunk)
            for chunk in chunk_pages(
                pages,
                chunk_size=200,
                chunk_overlap=20,
            )
        )

    return chunks


def cosine_similarity(
    left: list[float],
    right: list[float],
) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))

    if left_norm == 0 or right_norm == 0:
        return 0.0

    return dot / (left_norm * right_norm)


def ranked_chunks(
    question: str,
    corpus_chunks: list[tuple[str, TextChunk]],
    provider: EvaluationEmbeddingProvider,
) -> list[tuple[float, str, TextChunk]]:
    question_embedding = provider.embed_text(question)
    ranked = [
        (
            cosine_similarity(
                question_embedding,
                provider.embed_text(chunk.content),
            ),
            document,
            chunk,
        )
        for document, chunk in corpus_chunks
    ]

    return sorted(
        ranked,
        key=lambda item: (
            -item[0],
            item[1],
            item[2].page_number,
            item[2].chunk_index,
        ),
    )


@pytest.mark.parametrize(
    "case",
    EVALUATION_CASES["known_questions"],
    ids=lambda case: (
        f"{case['expected_document']}-"
        f"page-{case['expected_pages'][0]}"
    ),
)
def test_known_questions_retrieve_expected_page_in_memory(
    corpus_chunks: list[tuple[str, TextChunk]],
    case: dict,
) -> None:
    provider = EvaluationEmbeddingProvider()

    top_results = ranked_chunks(
        case["question"],
        corpus_chunks,
        provider,
    )[: case["top_k"]]

    assert any(
        document == case["expected_document"]
        and chunk.page_number in case["expected_pages"]
        for _score, document, chunk in top_results
    )


@pytest.mark.parametrize(
    "case",
    EVALUATION_CASES["unsupported_questions"],
    ids=["unsupported-ocean", "unsupported-football"],
)
def test_unsupported_questions_fail_support_threshold_in_memory(
    corpus_chunks: list[tuple[str, TextChunk]],
    case: dict,
) -> None:
    provider = EvaluationEmbeddingProvider()

    ranked = ranked_chunks(
        case["question"],
        corpus_chunks,
        provider,
    )

    max_similarity = max(score for score, _document, _chunk in ranked)

    assert max_similarity < settings.retrieval_min_similarity


def test_fixture_pdf_page_mapping_is_stable(cases: dict) -> None:
    expected_first_lines = {
        "employee_handbook.pdf": (
            "Remote work policy:",
            "Training reimbursement policy:",
            "Incident reporting policy:",
        ),
        "product_manual.pdf": (
            "Warranty policy:",
            "Battery guidance:",
            "Maintenance schedule:",
        ),
    }

    for document in cases["documents"]:
        pages = extract_pdf_pages(FIXTURE_ROOT / document["file"])

        assert len(pages) == len(
            expected_first_lines[document["file"]]
        )

        for index, page in enumerate(pages):
            assert page.text.startswith(
                expected_first_lines[document["file"]][index]
            )


def test_pgvector_evaluation_matches_expected_pages_when_database_available(
    cases: dict,
    tmp_path: Path,
) -> None:
    try:
        with engine.connect() as connection:
            connection.execute(select(1))
    except OperationalError:
        pytest.skip("PostgreSQL test database is not available")

    provider = EvaluationEmbeddingProvider()
    db = Session(engine)
    document_ids: list[int] = []
    suffix = uuid4().hex

    try:
        for fixture in cases["documents"]:
            source_path = FIXTURE_ROOT / fixture["file"]
            copied_path = (
                tmp_path
                / f"{suffix}-{fixture['file']}"
            )
            shutil.copyfile(source_path, copied_path)

            document = Document(
                filename=f"{suffix}-{fixture['file']}",
                original_filename=fixture["original_filename"],
                file_path=str(copied_path),
                status=DocumentStatus.UPLOADED,
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            document_ids.append(document.id)

            process_document(
                db,
                document,
                provider,
                page_chunker=lambda pages: chunk_pages(
                    pages,
                    chunk_size=200,
                    chunk_overlap=20,
                ),
            )

        for case in cases["known_questions"]:
            results = retrieve_relevant_chunks(
                db,
                case["question"],
                provider,
                top_k=case["top_k"],
            )

            assert any(
                result.document == case["expected_document"]
                and result.page_number in case["expected_pages"]
                for result in results
            )

        for case in cases["unsupported_questions"]:
            results = retrieve_relevant_chunks(
                db,
                case["question"],
                provider,
                top_k=5,
            )

            assert results
            assert max(
                result.similarity for result in results
            ) < settings.retrieval_min_similarity
    finally:
        db.rollback()

        if document_ids:
            db.execute(
                delete(Document).where(
                    Document.id.in_(document_ids)
                )
            )
            db.commit()

        db.close()
