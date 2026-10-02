from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services.embedding_service import EmbeddingProvider
from app.services.generation_service import (
    GenerationMessage,
    GenerationProvider,
)
from app.services.rag_prompt_service import (
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

    prompt = build_grounded_prompt(
        question,
        [
            RAGContextChunk(
                document_id=chunk.document_id,
                document=chunk.document,
                page_number=chunk.page_number,
                content=chunk.content,
            )
            for chunk in retrieved_chunks
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
