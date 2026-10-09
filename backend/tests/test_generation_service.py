from types import SimpleNamespace
import logging

import httpx
import pytest
from openai import APITimeoutError
from pydantic import SecretStr, ValidationError

from app.core.config import Settings, settings
from app.services.generation_service import (
    GenerationConfigurationError,
    GenerationInputError,
    GenerationMessage,
    GenerationProviderError,
    GenerationResponseError,
    GenerationTimeoutError,
    OpenAIGenerationProvider,
    build_generation_provider,
)


class FakeResponsesAPI:
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
    def __init__(self, responses_api: FakeResponsesAPI) -> None:
        self.responses = responses_api


def make_provider(response=None, error=None):
    api = FakeResponsesAPI(response=response, error=error)
    provider = OpenAIGenerationProvider(
        model="test-generation-model",
        api_key="test-key",
        timeout_seconds=1,
        client=FakeClient(api),
    )
    return provider, api


def test_generate_uses_responses_api_and_returns_trimmed_text() -> None:
    provider, api = make_provider(
        response=SimpleNamespace(output_text="  Grounded answer.  ")
    )

    result = provider.generate(
        [
            GenerationMessage(
                role="developer",
                content="Use supplied context only.",
            ),
            GenerationMessage(
                role="user",
                content="What is the warranty?",
            ),
        ]
    )

    assert result == "Grounded answer."
    assert api.calls == [
        {
            "model": "test-generation-model",
            "input": [
                {
                    "role": "developer",
                    "content": "Use supplied context only.",
                },
                {
                    "role": "user",
                    "content": "What is the warranty?",
                },
            ],
        }
    ]


def test_empty_message_list_is_rejected_before_provider_call() -> None:
    provider, api = make_provider(
        response=SimpleNamespace(output_text="unused")
    )

    with pytest.raises(
        GenerationInputError,
        match="at least one message",
    ):
        provider.generate([])

    assert api.calls == []


def test_blank_message_content_is_rejected_before_provider_call() -> None:
    provider, api = make_provider(
        response=SimpleNamespace(output_text="unused")
    )

    with pytest.raises(
        GenerationInputError,
        match="non-empty content",
    ):
        provider.generate(
            [GenerationMessage(role="user", content="   ")]
        )

    assert api.calls == []


def test_provider_error_is_mapped_to_controlled_error() -> None:
    provider, _ = make_provider(error=RuntimeError("provider detail"))

    with pytest.raises(
        GenerationProviderError,
        match="provider request failed",
    ):
        provider.generate(
            [GenerationMessage(role="user", content="Question")]
        )


def test_provider_timeout_has_specific_error() -> None:
    request = httpx.Request(
        "POST",
        "https://api.openai.com/v1/responses",
    )
    provider, _ = make_provider(
        error=APITimeoutError(request=request)
    )

    with pytest.raises(
        GenerationTimeoutError,
        match="timed out",
    ):
        provider.generate(
            [GenerationMessage(role="user", content="Question")]
        )


@pytest.mark.parametrize(
    "output_text",
    [None, "", "   "],
)
def test_empty_provider_output_is_rejected(output_text) -> None:
    provider, _ = make_provider(
        response=SimpleNamespace(output_text=output_text)
    )

    with pytest.raises(
        GenerationResponseError,
        match="no text output",
    ):
        provider.generate(
            [GenerationMessage(role="user", content="Question")]
        )


def test_factory_rejects_missing_openai_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", None)

    with pytest.raises(
        GenerationConfigurationError,
        match="OPENAI_API_KEY is required",
    ):
        build_generation_provider(
            client=FakeClient(FakeResponsesAPI())
        )


def test_factory_rejects_unsupported_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_provider", "unsupported")
    monkeypatch.setattr(
        settings,
        "openai_api_key",
        SecretStr("test-key"),
    )

    with pytest.raises(
        GenerationConfigurationError,
        match="Unsupported LLM provider",
    ):
        build_generation_provider(
            client=FakeClient(FakeResponsesAPI())
        )


def test_factory_builds_openai_provider_without_network_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeClient(FakeResponsesAPI())
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_model", "test-generation-model")
    monkeypatch.setattr(
        settings,
        "openai_api_key",
        SecretStr("test-key"),
    )

    provider = build_generation_provider(client=fake_client)

    assert isinstance(provider, OpenAIGenerationProvider)
    assert provider.model == "test-generation-model"


def test_llm_model_must_be_explicitly_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LLM_MODEL", raising=False)

    with pytest.raises(ValidationError):
        Settings(
            database_url=(
                "postgresql+psycopg://postgres:postgres@localhost:5432/test"
            ),
            _env_file=None,
        )



def test_generation_provider_logs_safe_duration_without_prompt(
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider, _ = make_provider(
        response=SimpleNamespace(output_text="Grounded answer.")
    )
    sensitive_prompt = "confidential retrieved context"

    with caplog.at_level(
        logging.INFO,
        logger="app.services.generation_service",
    ):
        provider.generate(
            [
                GenerationMessage(
                    role="user",
                    content=sensitive_prompt,
                )
            ]
        )

    record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None)
        == "provider.request.completed"
    )

    assert record.provider == "openai"
    assert record.operation == "generation"
    assert record.duration_ms >= 0
    assert sensitive_prompt not in caplog.text
    assert "Grounded answer." not in caplog.text


def test_generation_provider_failure_logs_error_type_not_secret(
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider, _ = make_provider(
        error=RuntimeError("secret-provider-message")
    )

    with caplog.at_level(
        logging.ERROR,
        logger="app.services.generation_service",
    ):
        with pytest.raises(GenerationProviderError):
            provider.generate(
                [
                    GenerationMessage(
                        role="user",
                        content="private question",
                    )
                ]
            )

    record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "provider.request.failed"
    )

    assert record.error_type == "RuntimeError"
    assert "secret-provider-message" not in caplog.text
    assert "private question" not in caplog.text
