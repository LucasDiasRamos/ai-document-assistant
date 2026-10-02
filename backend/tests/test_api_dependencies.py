import pytest

from fastapi import HTTPException

from app.api.dependencies import (
    get_embedding_provider_dependency,
    get_generation_provider_dependency,
)
from app.core.config import settings


def test_missing_embedding_configuration_returns_safe_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", None)

    with pytest.raises(HTTPException) as exc_info:
        get_embedding_provider_dependency()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Embedding provider is not configured"



def test_missing_generation_configuration_returns_safe_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", None)

    with pytest.raises(HTTPException) as exc_info:
        get_generation_provider_dependency()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Generation provider is not configured"
