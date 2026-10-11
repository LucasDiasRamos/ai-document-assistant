"""Integration coverage for token-scoped conversation history."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_embedding_provider_dependency, get_generation_provider_dependency
)
from app.core.database import engine, get_db
from app.main import app
from app.models.conversation import Conversation, ConversationMessage
from app.services.rag_prompt_service import RAGSource
from app.services.rag_service import RAGAnswer
import app.api.routes.conversations as conversation_routes


@pytest.fixture
def test_client(monkeypatch):
    try:
        with engine.connect() as conn:
            conn.execute(select(1))
    except OperationalError:
        pytest.skip("PostgreSQL test database is unavailable")

    def new_session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = new_session
    app.dependency_overrides[get_embedding_provider_dependency] = lambda: object()
    app.dependency_overrides[get_generation_provider_dependency] = lambda: object()
    monkeypatch.setattr(
        conversation_routes,
        "answer_question",
        lambda db, question, embedding_provider, generation_provider: RAGAnswer(
            answer="The warranty is 24 months.",
            sources=(RAGSource(document_id=123, document="manual.pdf", page_number=3),),
        ),
    )
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def bearer(token):
    return {"X-Conversation-Token": token}


def test_create_chat_reopen_and_delete_with_citations(test_client) -> None:
    created = test_client.post("/api/conversations")
    assert created.status_code == 201
    token = created.json()["token"]
    assert len(token) == 64
    assert token not in created.json()["expires_at"]

    first = test_client.post(
        "/api/conversations/current/chat",
        headers=bearer(token),
        json={"question": "What is the warranty?"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["sources"] == [
        {"document_id": 123, "document": "manual.pdf", "page": 3}
    ]
    second = test_client.post(
        "/api/conversations/current/chat",
        headers=bearer(token),
        json={"question": "Repeat that"},
    )
    assert second.status_code == 200

    history = test_client.get("/api/conversations/current", headers=bearer(token))
    assert history.status_code == 200
    assert [x["role"] for x in history.json()["messages"]] == [
        "user", "assistant", "user", "assistant"
    ]
    assert history.json()["messages"][1]["sources"][0]["page"] == 3
    assert history.json()["messages"][0]["sources"] == []

    with Session(engine) as db:
        assert db.get(Conversation, token) is None  # raw capability is not stored

    deletion = test_client.delete("/api/conversations/current", headers=bearer(token))
    assert deletion.status_code == 204
    assert test_client.get("/api/conversations/current", headers=bearer(token)).status_code == 404


def test_unknown_missing_and_expired_tokens_are_rejected(test_client) -> None:
    assert test_client.get("/api/conversations/current").status_code == 422
    assert test_client.get(
        "/api/conversations/current", headers=bearer("a" * 64)
    ).status_code == 404

    token = test_client.post("/api/conversations").json()["token"]
    from hashlib import sha256
    with Session(engine) as db:
        db.execute(
            update(Conversation)
            .where(Conversation.token_hash == sha256(token.encode()).hexdigest())
            .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
        db.commit()

    assert test_client.get("/api/conversations/current", headers=bearer(token)).status_code == 404
    assert test_client.post(
        "/api/conversations/current/chat",
        headers=bearer(token),
        json={"question": "Should not call the provider"},
    ).status_code == 404


def test_conversations_are_isolated_by_unpredictable_bearer(test_client) -> None:
    first = test_client.post("/api/conversations").json()["token"]
    second = test_client.post("/api/conversations").json()["token"]
    assert first != second
    response = test_client.post(
        "/api/conversations/current/chat",
        headers=bearer(first),
        json={"question": "First conversation"},
    )
    assert response.status_code == 200
    assert len(test_client.get(
        "/api/conversations/current", headers=bearer(first)
    ).json()["messages"]) == 2
    assert test_client.get(
        "/api/conversations/current", headers=bearer(second)
    ).json()["messages"] == []
    for token in (first, second):
        test_client.delete("/api/conversations/current", headers=bearer(token))


def test_history_limit_does_not_grow_unbounded(test_client, monkeypatch) -> None:
    monkeypatch.setattr(conversation_routes, "MAX_MESSAGES", 2)
    token = test_client.post("/api/conversations").json()["token"]
    for expected_status in (200, 409):
        assert test_client.post(
            "/api/conversations/current/chat",
            headers=bearer(token),
            json={"question": "Bounded question"},
        ).status_code == expected_status
    assert len(test_client.get(
        "/api/conversations/current", headers=bearer(token)
    ).json()["messages"]) == 2
    test_client.delete("/api/conversations/current", headers=bearer(token))
