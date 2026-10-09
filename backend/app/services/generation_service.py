from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import logging
from time import perf_counter
from typing import Any, Literal, Protocol

from openai import APITimeoutError, OpenAI

from app.core.config import settings
from app.core.observability import elapsed_ms, log_event


GenerationRole = Literal["system", "developer", "user", "assistant"]
_ALLOWED_ROLES = {"system", "developer", "user", "assistant"}
logger = logging.getLogger(__name__)


class GenerationError(RuntimeError):
    """Base error for text generation operations."""


class GenerationConfigurationError(GenerationError):
    pass


class GenerationInputError(GenerationError):
    pass


class GenerationProviderError(GenerationError):
    pass


class GenerationTimeoutError(GenerationProviderError):
    pass


class GenerationResponseError(GenerationError):
    pass


@dataclass(frozen=True, slots=True)
class GenerationMessage:
    role: GenerationRole
    content: str


class GenerationProvider(Protocol):
    def generate(
        self,
        messages: Sequence[GenerationMessage],
    ) -> str:
        ...


class OpenAIGenerationProvider:
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        timeout_seconds: float,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self._client = client or OpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
        )

    def generate(
        self,
        messages: Sequence[GenerationMessage],
    ) -> str:
        prepared_messages = _prepare_messages(messages)

        started_at = perf_counter()

        try:
            response = self._client.responses.create(
                model=self.model,
                input=prepared_messages,
            )
        except APITimeoutError as exc:
            log_event(
                logger,
                logging.ERROR,
                "provider.request.failed",
                provider="openai",
                operation="generation",
                duration_ms=elapsed_ms(started_at),
                error_type=type(exc).__name__,
            )
            raise GenerationTimeoutError(
                "Generation provider request timed out"
            ) from exc
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "provider.request.failed",
                provider="openai",
                operation="generation",
                duration_ms=elapsed_ms(started_at),
                error_type=type(exc).__name__,
            )
            raise GenerationProviderError(
                "Generation provider request failed"
            ) from exc

        log_event(
            logger,
            logging.INFO,
            "provider.request.completed",
            provider="openai",
            operation="generation",
            duration_ms=elapsed_ms(started_at),
        )

        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            raise GenerationResponseError(
                "Generation provider returned no text output"
            )

        return output_text.strip()


def build_generation_provider(
    *,
    client: Any | None = None,
) -> GenerationProvider:
    provider_name = settings.llm_provider.strip().lower()

    if provider_name != "openai":
        raise GenerationConfigurationError(
            f"Unsupported LLM provider: {settings.llm_provider}"
        )

    if settings.openai_api_key is None:
        raise GenerationConfigurationError(
            "OPENAI_API_KEY is required for the OpenAI LLM provider"
        )

    api_key = settings.openai_api_key.get_secret_value().strip()
    if not api_key:
        raise GenerationConfigurationError(
            "OPENAI_API_KEY is required for the OpenAI LLM provider"
        )

    return OpenAIGenerationProvider(
        model=settings.llm_model,
        api_key=api_key,
        timeout_seconds=settings.llm_timeout_seconds,
        client=client,
    )


def _prepare_messages(
    messages: Sequence[GenerationMessage],
) -> list[dict[str, str]]:
    if not messages:
        raise GenerationInputError(
            "Generation requires at least one message"
        )

    prepared: list[dict[str, str]] = []

    for message in messages:
        if message.role not in _ALLOWED_ROLES:
            raise GenerationInputError(
                f"Unsupported generation message role: {message.role}"
            )

        content = message.content.strip()
        if not content:
            raise GenerationInputError(
                "Generation messages must contain non-empty content"
            )

        prepared.append(
            {
                "role": message.role,
                "content": content,
            }
        )

    return prepared
