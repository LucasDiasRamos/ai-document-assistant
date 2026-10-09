"""CI-only FastAPI entrypoint exercising real PostgreSQL/pgvector and PDF ingest.

Run ONLY for local browser E2E or disposable CI databases. It replaces paid
AI providers with deterministic fakes; it must never be deployed publicly.
"""
from __future__ import annotations

import os
from collections.abc import Sequence

if os.environ.get("ENABLE_DETERMINISTIC_E2E") != "1":
    raise RuntimeError("E2E app requires ENABLE_DETERMINISTIC_E2E=1")

from app.api.dependencies import (
    get_embedding_provider_dependency,
    get_generation_provider_dependency,
)
from app.core.config import settings
from app.main import app
from app.models.document_chunk import EMBEDDING_DIMENSION
from app.services.generation_service import GenerationMessage

if settings.app_environment != "development":
    raise RuntimeError("E2E providers may only run in development mode")


class DeterministicEmbeddings:
    dimension = EMBEDDING_DIMENSION
    _concepts = {
        "remote": 0,
        "training": 1,
        "incident": 2,
        "warranty": 3,
        "battery": 4,
        "maintenance": 5,
    }

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        normalized = text.lower()
        matched = False
        for keyword, position in self._concepts.items():
            if keyword in normalized:
                vector[position] = 1.0
                matched = True
        if not matched:
            vector[100] = 1.0
        return vector

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]


class DeterministicGeneration:
    def generate(self, messages: Sequence[GenerationMessage]) -> str:
        if not messages or "remote" not in messages[-1].content.lower():
            raise ValueError("Unexpected E2E question")
        return "The employee handbook includes the remote-work policy."


embeddings = DeterministicEmbeddings()
generation = DeterministicGeneration()
app.dependency_overrides[get_embedding_provider_dependency] = lambda: embeddings
app.dependency_overrides[get_generation_provider_dependency] = lambda: generation
