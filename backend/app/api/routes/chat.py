from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_embedding_provider_dependency,
    get_generation_provider_dependency,
)
from app.core.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse, ChatSource
from app.schemas.document import APIError
from app.services.embedding_service import EmbeddingError, EmbeddingProvider
from app.services.generation_service import GenerationError, GenerationProvider
from app.services.rag_service import answer_question
from app.services.retrieval_service import RetrievalError

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(
    "",
    response_model=ChatResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": APIError},
    },
)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(
        get_embedding_provider_dependency
    ),
    generation_provider: GenerationProvider = Depends(
        get_generation_provider_dependency
    ),
) -> ChatResponse:
    try:
        result = answer_question(
            db,
            request.question,
            embedding_provider,
            generation_provider,
        )
    except (EmbeddingError, RetrievalError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document retrieval is temporarily unavailable",
        ) from exc
    except GenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Answer generation is temporarily unavailable",
        ) from exc

    return ChatResponse(
        answer=result.answer,
        sources=[
            ChatSource(
                document_id=source.document_id,
                document=source.document,
                page=source.page_number,
            )
            for source in result.sources
        ],
    )
