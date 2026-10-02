from fastapi import HTTPException, status

from app.services.embedding_service import (
    EmbeddingConfigurationError,
    EmbeddingProvider,
    build_embedding_provider,
)
from app.services.generation_service import (
    GenerationConfigurationError,
    GenerationProvider,
    build_generation_provider,
)


def get_embedding_provider_dependency() -> EmbeddingProvider:
    try:
        return build_embedding_provider()
    except EmbeddingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding provider is not configured",
        ) from exc


def get_generation_provider_dependency() -> GenerationProvider:
    try:
        return build_generation_provider()
    except GenerationConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Generation provider is not configured",
        ) from exc
