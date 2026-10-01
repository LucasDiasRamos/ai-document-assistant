from app.core.config import settings
from app.models import Document, DocumentChunk, DocumentStatus


def test_document_status_values_are_stable() -> None:
    assert [status.value for status in DocumentStatus] == [
        "uploaded",
        "processing",
        "processed",
        "failed",
    ]


def test_document_chunk_embedding_dimension_matches_settings() -> None:
    embedding_type = DocumentChunk.__table__.c.embedding.type
    assert embedding_type.dim == settings.embedding_dimension


def test_document_chunks_use_database_cascade() -> None:
    foreign_key = next(
        iter(DocumentChunk.__table__.c.document_id.foreign_keys)
    )
    assert foreign_key.ondelete == "CASCADE"
    assert Document.chunks.property.cascade.delete_orphan is True


def test_document_chunk_constraints_are_present() -> None:
    constraint_names = {
        constraint.name
        for constraint in DocumentChunk.__table__.constraints
        if constraint.name is not None
    }

    assert "uq_document_chunks_document_chunk_index" in constraint_names
    assert "ck_document_chunks_page_number" in constraint_names
    assert "ck_document_chunks_chunk_index" in constraint_names
