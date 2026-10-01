from fastapi import HTTPException, status

from app.services.embedding_service import (
    EmbeddingConfigurationError,
    EmbeddingProvider,
    build_embedding_provider,
)


def get_embedding_provider_dependency() -> EmbeddingProvider:
    try:
        return build_embedding_provider()
    except EmbeddingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding provider is not configured",
        ) from exc
