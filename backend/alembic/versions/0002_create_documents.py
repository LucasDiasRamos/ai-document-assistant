"""Create documents table.

Revision ID: 0002_create_documents
Revises: 0001_enable_pgvector
Create Date: 2026-10-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_create_documents"
down_revision: Union[str, Sequence[str], None] = "0001_enable_pgvector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


document_status = sa.Enum(
    "uploaded",
    "processing",
    "processed",
    "failed",
    name="document_status",
    native_enum=False,
    create_constraint=True,
    length=20,
)


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column(
            "status",
            document_status,
            server_default="uploaded",
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("filename"),
        sa.UniqueConstraint("file_path"),
    )
    op.create_index("ix_documents_status", "documents", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_table("documents")
