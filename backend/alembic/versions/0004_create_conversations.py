"""Create bounded, token-scoped conversations.

Revision ID: 0004_create_conversations
Revises: 0003_create_document_chunks
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_create_conversations"
down_revision: Union[str, Sequence[str], None] = "0003_create_document_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_hash", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=9), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("position >= 0", name="ck_conversation_message_position"),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_conversation_message_role"),
        sa.ForeignKeyConstraint(["conversation_hash"], ["conversations.token_hash"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_hash", "position", name="uq_conversation_message_position"),
    )
    op.create_index("ix_conversation_messages_conversation_hash", "conversation_messages", ["conversation_hash"])


def downgrade() -> None:
    op.drop_index("ix_conversation_messages_conversation_hash", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_table("conversations")
