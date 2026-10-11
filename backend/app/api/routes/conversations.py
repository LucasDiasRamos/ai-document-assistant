"""Anonymous demo conversation history behind a high-entropy bearer capability.

This is NOT user authentication or multi-tenant isolation. The public demo
must remain restricted to synthetic documents and protected at the edge.
History is NOT forwarded to the model (zero additional history tokens).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_hex
from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_embedding_provider_dependency,
    get_generation_provider_dependency,
)
from app.api.errors import APIErrorCode, APIException
from app.core.database import get_db
from app.models.conversation import Conversation, ConversationMessage
from app.schemas.chat import ChatRequest, ChatResponse, ChatSource
from app.schemas.conversation import (
    ConversationCreated,
    ConversationHistory,
    ConversationMessageView,
)
from app.services.embedding_service import EmbeddingError, EmbeddingProvider
from app.services.generation_service import GenerationError, GenerationProvider
from app.services.rag_service import answer_question
from app.services.retrieval_service import RetrievalError

router = APIRouter(prefix="/conversations", tags=["Conversations"])
TOKEN_HEADER = Annotated[
    str, Header(alias="X-Conversation-Token", min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
]
MAX_MESSAGES = 100
RETENTION_DAYS = 7


def _lookup(db: Session, token: str, *, lock: bool = False) -> Conversation:
    digest = sha256(token.encode("ascii")).hexdigest()
    query = select(Conversation).where(
        Conversation.token_hash == digest,
        Conversation.expires_at > datetime.now(timezone.utc),
    )
    if lock:
        query = query.with_for_update()
    conversation = db.scalar(query)
    if conversation is None:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=APIErrorCode.HTTP_ERROR,
            detail="Conversation not found or expired",
        )
    return conversation


@router.post("", status_code=201, response_model=ConversationCreated)
def create_conversation(db: Session = Depends(get_db)) -> ConversationCreated:
    token = token_hex(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=RETENTION_DAYS)
    db.add(Conversation(
        token_hash=sha256(token.encode("ascii")).hexdigest(),
        expires_at=expires_at,
    ))
    db.commit()
    return ConversationCreated(token=token, expires_at=expires_at)


@router.get("/current", response_model=ConversationHistory)
def read_conversation(
    token: TOKEN_HEADER,
    db: Session = Depends(get_db),
) -> ConversationHistory:
    conversation = _lookup(db, token)
    items = db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_hash == conversation.token_hash)
        .order_by(ConversationMessage.position.asc())
        .limit(MAX_MESSAGES)
    ).all()
    return ConversationHistory(
        expires_at=conversation.expires_at,
        messages=[
            ConversationMessageView(
                role=item.role,
                content=item.content,
                sources=[ChatSource.model_validate(source) for source in item.sources],
            )
            for item in items
        ],
    )


@router.delete("/current", status_code=204)
def delete_conversation(
    token: TOKEN_HEADER,
    db: Session = Depends(get_db),
) -> None:
    conversation = _lookup(db, token)
    db.delete(conversation)
    db.commit()


@router.post("/current/chat", response_model=ChatResponse)
def chat_in_conversation(
    request: ChatRequest,
    token: TOKEN_HEADER,
    db: Session = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider_dependency),
    generation_provider: GenerationProvider = Depends(get_generation_provider_dependency),
) -> ChatResponse:
    # Reject unknown tokens before expensive provider requests.
    _lookup(db, token)
    db.rollback()

    try:
        result = answer_question(db, request.question, embedding_provider, generation_provider)
    except (EmbeddingError, RetrievalError) as exc:
        raise APIException(
            status_code=503, code=APIErrorCode.PROVIDER_UNAVAILABLE,
            detail="Document retrieval is temporarily unavailable",
        ) from exc
    except GenerationError as exc:
        raise APIException(
            status_code=503, code=APIErrorCode.PROVIDER_UNAVAILABLE,
            detail="Answer generation is temporarily unavailable",
        ) from exc

    sources = [
        ChatSource(document_id=x.document_id, document=x.document, page=x.page_number)
        for x in result.sources
    ]

    # Lock the conversation row while assigning monotonically increasing
    # positions, so concurrent tabs cannot overwrite each other.
    conversation = _lookup(db, token, lock=True)
    last_position = db.scalar(
        select(func.max(ConversationMessage.position)).where(
            ConversationMessage.conversation_hash == conversation.token_hash
        )
    )
    next_position = 0 if last_position is None else last_position + 1
    if next_position + 2 > MAX_MESSAGES:
        db.rollback()
        raise APIException(
            status_code=409, code=APIErrorCode.VALIDATION_ERROR,
            detail="Conversation history limit reached. Start a new chat.",
        )
    db.add_all([
        ConversationMessage(
            conversation_hash=conversation.token_hash,
            position=next_position,
            role="user",
            content=request.question,
            sources=[],
        ),
        ConversationMessage(
            conversation_hash=conversation.token_hash,
            position=next_position + 1,
            role="assistant",
            content=result.answer,
            sources=[x.model_dump() for x in sources],
        ),
    ])
    db.commit()
    return ChatResponse(answer=result.answer, sources=sources)
