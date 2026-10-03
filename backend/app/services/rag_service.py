from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.embedding_service import EmbeddingProvider
from app.services.generation_service import (
    GenerationMessage,
    GenerationProvider,
)
from app.services.rag_prompt_service import (
    INSUFFICIENT_CONTEXT_MESSAGE,
    RAGContextChunk,
    RAGSource,
    build_grounded_prompt,
)
from app.services.retrieval_service import retrieve_relevant_chunks


@dataclass(frozen=True, slots=True)
class RAGAnswer:
    answer: str
    sources: tuple[RAGSource, ...]


def answer_question(
    db: Session,
    question: str,
    embedding_provider: EmbeddingProvider,
    generation_provider: GenerationProvider,
) -> RAGAnswer:
    retrieved_chunks = retrieve_relevant_chunks(
        db,
        question,
        embedding_provider,
    )
    db.rollback()

    supported_chunks = [
        chunk
        for chunk in retrieved_chunks
        if chunk.similarity >= settings.retrieval_min_similarity
    ]

    if not supported_chunks:
        return RAGAnswer(
            answer=INSUFFICIENT_CONTEXT_MESSAGE,
            sources=(),
        )

    prompt = build_grounded_prompt(
        question,
        [
            RAGContextChunk(
                document_id=chunk.document_id,
                document=chunk.document,
                page_number=chunk.page_number,
                content=chunk.content,
            )
            for chunk in supported_chunks
        ],
    )

    answer = generation_provider.generate(
        [
            GenerationMessage(
                role="developer",
                content=prompt.developer_message,
            ),
            GenerationMessage(
                role="user",
                content=prompt.user_message,
            ),
        ]
    )

    return RAGAnswer(
        answer=answer,
        sources=prompt.sources,
    )
