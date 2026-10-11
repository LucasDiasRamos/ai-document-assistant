"""Token-scoped conversation history: tokens are never stored in plaintext."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.conversation import ConversationMessage


class Conversation(Base):
    __tablename__ = "conversations"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ConversationMessage.position",
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        UniqueConstraint("conversation_hash", "position", name="uq_conversation_message_position"),
        CheckConstraint("position >= 0", name="ck_conversation_message_position"),
        CheckConstraint("role IN ('user', 'assistant')", name="ck_conversation_message_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_hash: Mapped[str] = mapped_column(
        String(64), ForeignKey("conversations.token_hash", ondelete="CASCADE"),
        nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(String(9), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
