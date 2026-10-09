from io import BytesIO

import pytest
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.datastructures import Headers

from app.core.config import Settings, settings
from app.main import create_app
from app.middleware.rate_limit import DemoRateLimitMiddleware
from app.services.document_service import (
    DocumentUploadValidationError,
    _validate_upload,
)


def test_production_requires_explicit_https_cors_origins() -> None:
    baseline = {
        "database_url": "postgresql+psycopg://local:local@localhost/test",
        "llm_model": "test",
    }
    with pytest.raises(ValidationError, match="explicit CORS_ALLOWED_ORIGINS"):
        Settings(**baseline, app_environment="production", cors_allowed_origins=[])
    with pytest.raises(ValidationError, match="must use HTTPS"):
        Settings(
            **baseline,
            app_environment="production",
            cors_allowed_origins=["http://frontend.example.com"],
        )
    with pytest.raises(ValidationError, match="exact HTTP"):
        Settings(**baseline, cors_allowed_origins=["*"])


def test_production_disables_schema_ui_and_debug(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(
        settings, "cors_allowed_origins", ["https://frontend.example.com"]
    )
    isolated_app = create_app()
    with TestClient(isolated_app) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/health").json() == {"status": "ok"}
    assert isolated_app.debug is False


def test_cors_denies_unknown_origin_and_allows_configured_origin(monkeypatch) -> None:
    monkeypatch.setattr(
        settings, "cors_allowed_origins", ["https://frontend.example.com"]
    )
    isolated_app = create_app()
    def preflight(client: TestClient, origin: str):
        return client.options(
            "/api/chat",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    with TestClient(isolated_app) as client:
        denied = preflight(client, "https://attacker.example.com")
        allowed = preflight(client, "https://frontend.example.com")

    assert denied.status_code == 400
    assert denied.headers.get("access-control-allow-origin") is None
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == (
        "https://frontend.example.com"
    )


@pytest.mark.parametrize(
    "filename",
    ["../private.pdf", "dir/sub.pdf", "folder\\private.pdf", "malicious\x00.pdf"],
)
def test_upload_rejects_unsafe_filenames(filename: str) -> None:
    file = UploadFile(
        filename=filename,
        file=BytesIO(b"%PDF-1.7\n%%EOF"),
        headers=Headers({"content-type": "application/pdf"}),
    )
    with pytest.raises(
        DocumentUploadValidationError, match="Filename contains unsafe"
    ):
        _validate_upload(file)


def test_expensive_routes_are_bounded_and_forwarded_headers_are_untrusted(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "chat_requests_per_minute", 2)
    monkeypatch.setattr(settings, "upload_requests_per_minute", 1)
    app = FastAPI()
    app.add_middleware(DemoRateLimitMiddleware)

    @app.post("/api/chat")
    def chat() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/documents")
    def upload() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app) as client:
        assert client.post("/api/chat").status_code == 200
        assert client.post("/api/chat").status_code == 200
        rejected = client.post(
            "/api/chat", headers={"X-Forwarded-For": "198.51.100.10"}
        )
        assert rejected.status_code == 429
        assert rejected.json()["code"] == "rate_limited"
        assert int(rejected.headers["Retry-After"]) >= 1
        assert client.post("/api/documents").status_code == 200
        assert client.post("/api/documents").status_code == 429
        assert client.get("/health").status_code == 200
