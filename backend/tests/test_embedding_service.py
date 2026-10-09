from types import SimpleNamespace
import logging

import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.models.document_chunk import EMBEDDING_DIMENSION
from app.services.embedding_service import (
    EmbeddingConfigurationError,
    EmbeddingDimensionError,
    EmbeddingInputError,
    EmbeddingProviderError,
    EmbeddingResponseError,
    OPENAI_EMBEDDING_BATCH_SIZE,
    OpenAIEmbeddingProvider,
    build_embedding_provider,
)


def vector(value: float, dimension: int = EMBEDDING_DIMENSION) -> list[float]:
    return [value] * dimension


class FakeEmbeddingsAPI:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)

        if self.error is not None:
            raise self.error

        return self.response


class FakeClient:
    def __init__(self, embeddings_api: FakeEmbeddingsAPI) -> None:
        self.embeddings = embeddings_api


def make_provider(response) -> tuple[OpenAIEmbeddingProvider, FakeEmbeddingsAPI]:
    embeddings_api = FakeEmbeddingsAPI(response=response)
    provider = OpenAIEmbeddingProvider(
        model="text-embedding-3-small",
        api_key="test-key",
        timeout_seconds=1,
        client=FakeClient(embeddings_api),
    )
    return provider, embeddings_api


def test_embed_text_returns_schema_sized_vector() -> None:
    response = SimpleNamespace(
        data=[
            SimpleNamespace(
                index=0,
                embedding=vector(0.25),
            )
        ]
    )
    provider, api = make_provider(response)

    result = provider.embed_text("hello")

    assert result == vector(0.25)
    assert api.calls == [
        {
            "model": "text-embedding-3-small",
            "input": ["hello"],
            "dimensions": EMBEDDING_DIMENSION,
        }
    ]


def test_embed_batch_preserves_input_order_using_response_indexes() -> None:
    response = SimpleNamespace(
        data=[
            SimpleNamespace(index=1, embedding=vector(2.0)),
            SimpleNamespace(index=0, embedding=vector(1.0)),
        ]
    )
    provider, _ = make_provider(response)

    result = provider.embed_batch(["first", "second"])

    assert result[0][0] == 1.0
    assert result[1][0] == 2.0


def test_empty_batch_returns_without_provider_call() -> None:
    response = SimpleNamespace(data=[])
    provider, api = make_provider(response)

    assert provider.embed_batch([]) == []
    assert api.calls == []


def test_blank_embedding_input_is_rejected_before_provider_call() -> None:
    response = SimpleNamespace(data=[])
    provider, api = make_provider(response)

    with pytest.raises(EmbeddingInputError, match="non-empty"):
        provider.embed_batch(["valid", "   "])

    assert api.calls == []


def test_provider_failure_becomes_controlled_error() -> None:
    api = FakeEmbeddingsAPI(error=RuntimeError("network unavailable"))
    provider = OpenAIEmbeddingProvider(
        model="text-embedding-3-small",
        api_key="test-key",
        timeout_seconds=1,
        client=FakeClient(api),
    )

    with pytest.raises(
        EmbeddingProviderError,
        match="provider request failed",
    ):
        provider.embed_text("hello")


def test_wrong_embedding_dimension_is_rejected() -> None:
    response = SimpleNamespace(
        data=[
            SimpleNamespace(
                index=0,
                embedding=vector(0.1, EMBEDDING_DIMENSION - 1),
            )
        ]
    )
    provider, _ = make_provider(response)

    with pytest.raises(
        EmbeddingDimensionError,
        match="does not match database schema",
    ):
        provider.embed_text("hello")


def test_unexpected_result_count_is_rejected() -> None:
    response = SimpleNamespace(data=[])
    provider, _ = make_provider(response)

    with pytest.raises(
        EmbeddingResponseError,
        match="unexpected result count",
    ):
        provider.embed_text("hello")


def test_invalid_response_indexes_are_rejected() -> None:
    response = SimpleNamespace(
        data=[
            SimpleNamespace(index=1, embedding=vector(1.0)),
        ]
    )
    provider, _ = make_provider(response)

    with pytest.raises(
        EmbeddingResponseError,
        match="invalid result indexes",
    ):
        provider.embed_text("hello")


def test_unsupported_openai_embedding_model_is_rejected() -> None:
    with pytest.raises(
        EmbeddingConfigurationError,
        match="Unsupported OpenAI embedding model",
    ):
        OpenAIEmbeddingProvider(
            model="unknown-model",
            api_key="test-key",
            timeout_seconds=1,
            client=FakeClient(FakeEmbeddingsAPI()),
        )


def test_schema_dimension_is_explicitly_requested_from_large_model() -> None:
    response = SimpleNamespace(
        data=[
            SimpleNamespace(
                index=0,
                embedding=vector(0.4),
            )
        ]
    )
    api = FakeEmbeddingsAPI(response=response)
    provider = OpenAIEmbeddingProvider(
        model="text-embedding-3-large",
        api_key="test-key",
        timeout_seconds=1,
        client=FakeClient(api),
    )

    provider.embed_text("hello")

    assert api.calls[0]["dimensions"] == EMBEDDING_DIMENSION


def test_factory_rejects_missing_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", None)

    with pytest.raises(
        EmbeddingConfigurationError,
        match="OPENAI_API_KEY is required",
    ):
        build_embedding_provider(client=FakeClient(FakeEmbeddingsAPI()))


def test_factory_rejects_unsupported_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "unsupported")
    monkeypatch.setattr(settings, "openai_api_key", SecretStr("test-key"))

    with pytest.raises(
        EmbeddingConfigurationError,
        match="Unsupported embedding provider",
    ):
        build_embedding_provider(client=FakeClient(FakeEmbeddingsAPI()))


def test_factory_builds_openai_provider_without_network_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeClient(FakeEmbeddingsAPI())
    monkeypatch.setattr(settings, "embedding_provider", "openai")
    monkeypatch.setattr(settings, "embedding_model", "text-embedding-3-small")
    monkeypatch.setattr(settings, "openai_api_key", SecretStr("test-key"))

    provider = build_embedding_provider(client=fake_client)

    assert isinstance(provider, OpenAIEmbeddingProvider)
    assert provider.dimension == EMBEDDING_DIMENSION


def test_openai_provider_dimension_cannot_be_overridden() -> None:
    with pytest.raises(TypeError, match="dimension"):
        OpenAIEmbeddingProvider(
            model="text-embedding-3-small",
            api_key="test-key",
            timeout_seconds=1,
            client=FakeClient(FakeEmbeddingsAPI()),
            dimension=512,
        )


def test_large_batch_is_partitioned_and_preserves_global_order() -> None:
    total = OPENAI_EMBEDDING_BATCH_SIZE + 7

    class PartitioningEmbeddingsAPI:
        def __init__(self) -> None:
            self.calls = []

        def create(self, **kwargs):
            batch = kwargs["input"]
            self.calls.append(kwargs)
            call_offset = sum(
                len(previous["input"])
                for previous in self.calls[:-1]
            )
            return SimpleNamespace(
                data=[
                    SimpleNamespace(
                        index=index,
                        embedding=vector(float(call_offset + index)),
                    )
                    for index, _ in enumerate(batch)
                ]
            )

    api = PartitioningEmbeddingsAPI()
    provider = OpenAIEmbeddingProvider(
        model="text-embedding-3-small",
        api_key="test-key",
        timeout_seconds=1,
        client=FakeClient(api),
    )

    result = provider.embed_batch(
        [f"text-{index}" for index in range(total)]
    )

    assert [len(call["input"]) for call in api.calls] == [
        OPENAI_EMBEDDING_BATCH_SIZE,
        7,
    ]
    assert len(result) == total
    assert [item[0] for item in result] == [
        float(index) for index in range(total)
    ]



def test_embedding_provider_logs_safe_duration_without_input(
    caplog: pytest.LogCaptureFixture,
) -> None:
    response = SimpleNamespace(
        data=[
            SimpleNamespace(
                index=0,
                embedding=vector(0.25),
            )
        ]
    )
    provider, _ = make_provider(response)
    sensitive_input = "confidential document content"

    with caplog.at_level(
        logging.INFO,
        logger="app.services.embedding_service",
    ):
        provider.embed_text(sensitive_input)

    record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None)
        == "provider.request.completed"
    )

    assert record.provider == "openai"
    assert record.operation == "embedding"
    assert record.result_count == 1
    assert record.duration_ms >= 0
    assert sensitive_input not in caplog.text


def test_embedding_provider_failure_logs_error_type_not_secret(
    caplog: pytest.LogCaptureFixture,
) -> None:
    api = FakeEmbeddingsAPI(
        error=RuntimeError("secret-provider-message")
    )
    provider = OpenAIEmbeddingProvider(
        model="text-embedding-3-small",
        api_key="super-secret-key",
        timeout_seconds=1,
        client=FakeClient(api),
    )

    with caplog.at_level(
        logging.ERROR,
        logger="app.services.embedding_service",
    ):
        with pytest.raises(EmbeddingProviderError):
            provider.embed_text("private input")

    record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "provider.request.failed"
    )

    assert record.error_type == "RuntimeError"
    assert "secret-provider-message" not in caplog.text
    assert "super-secret-key" not in caplog.text
    assert "private input" not in caplog.text
