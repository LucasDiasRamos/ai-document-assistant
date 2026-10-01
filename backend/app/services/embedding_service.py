from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from openai import OpenAI

from app.core.config import settings
from app.models.document_chunk import EMBEDDING_DIMENSION


OPENAI_MODEL_MAX_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
}


class EmbeddingError(RuntimeError):
    """Base error for embedding operations."""


class EmbeddingConfigurationError(EmbeddingError):
    pass


class EmbeddingInputError(EmbeddingError):
    pass


class EmbeddingProviderError(EmbeddingError):
    pass


class EmbeddingResponseError(EmbeddingError):
    pass


class EmbeddingDimensionError(EmbeddingResponseError):
    pass


class EmbeddingProvider(Protocol):
    dimension: int

    def embed_text(self, text: str) -> list[float]:
        ...

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        ...


class OpenAIEmbeddingProvider:
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        timeout_seconds: float,
        client: Any | None = None,
        dimension: int = EMBEDDING_DIMENSION,
    ) -> None:
        self.model = model
        self.dimension = dimension

        self._validate_model_dimension()

        self._client = client or OpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
        )

    def embed_text(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        batch = list(texts)

        if not batch:
            return []

        if any(not text.strip() for text in batch):
            raise EmbeddingInputError(
                "Embedding input must contain non-empty text"
            )

        try:
            response = self._client.embeddings.create(
                model=self.model,
                input=batch,
                dimensions=self.dimension,
            )
        except Exception as exc:
            raise EmbeddingProviderError(
                "Embedding provider request failed"
            ) from exc

        data = sorted(response.data, key=lambda item: item.index)

        if len(data) != len(batch):
            raise EmbeddingResponseError(
                "Embedding provider returned an unexpected result count"
            )

        expected_indexes = list(range(len(batch)))
        returned_indexes = [item.index for item in data]
        if returned_indexes != expected_indexes:
            raise EmbeddingResponseError(
                "Embedding provider returned invalid result indexes"
            )

        embeddings: list[list[float]] = []

        for item in data:
            vector = list(item.embedding)

            if len(vector) != self.dimension:
                raise EmbeddingDimensionError(
                    "Embedding dimension does not match database schema: "
                    f"expected {self.dimension}, received {len(vector)}"
                )

            embeddings.append(vector)

        return embeddings

    def _validate_model_dimension(self) -> None:
        max_dimension = OPENAI_MODEL_MAX_DIMENSIONS.get(self.model)

        if max_dimension is None:
            raise EmbeddingConfigurationError(
                f"Unsupported OpenAI embedding model: {self.model}"
            )

        if self.dimension > max_dimension:
            raise EmbeddingConfigurationError(
                "Configured embedding model cannot produce the database "
                f"schema dimension of {self.dimension}"
            )


def build_embedding_provider(
    *,
    client: Any | None = None,
) -> EmbeddingProvider:
    provider_name = settings.embedding_provider.strip().lower()

    if provider_name != "openai":
        raise EmbeddingConfigurationError(
            f"Unsupported embedding provider: {settings.embedding_provider}"
        )

    if settings.openai_api_key is None:
        raise EmbeddingConfigurationError(
            "OPENAI_API_KEY is required for the OpenAI embedding provider"
        )

    api_key = settings.openai_api_key.get_secret_value().strip()
    if not api_key:
        raise EmbeddingConfigurationError(
            "OPENAI_API_KEY is required for the OpenAI embedding provider"
        )

    return OpenAIEmbeddingProvider(
        model=settings.embedding_model,
        api_key=api_key,
        timeout_seconds=settings.embedding_timeout_seconds,
        client=client,
    )
