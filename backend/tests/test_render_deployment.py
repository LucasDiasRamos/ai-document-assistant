from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("input_url", "expected_url"),
    [
        (
            "postgresql://user:pass@private-host:5432/app",
            "postgresql+psycopg://user:pass@private-host:5432/app",
        ),
        (
            "postgres://user:pass@private-host/app",
            "postgresql+psycopg://user:pass@private-host/app",
        ),
        (
            "postgresql+psycopg://user:pass@localhost/app",
            "postgresql+psycopg://user:pass@localhost/app",
        ),
    ],
)
def test_normalizes_managed_database_urls(input_url: str, expected_url: str) -> None:
    options = Settings(
        database_url=input_url,
        llm_model="test",
        _env_file=None,
    )
    assert options.database_url == expected_url


def test_production_requires_absolute_persistent_storage_directory() -> None:
    with pytest.raises(ValidationError, match="absolute STORAGE_ROOT"):
        Settings(
            database_url="postgresql://user:pass@localhost/app",
            llm_model="test",
            storage_root="../storage",
            app_environment="production",
            cors_allowed_origins=["https://frontend.example.com"],
            _env_file=None,
        )

    options = Settings(
        database_url="postgresql://user:pass@localhost/app",
        llm_model="test",
        storage_root="/app/storage",
        app_environment="production",
        cors_allowed_origins=["https://frontend.example.com"],
        _env_file=None,
    )
    assert options.storage_root == Path("/app/storage")


def test_deployment_blueprint_requires_persistent_storage_and_private_db() -> None:
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "autoDeployTrigger: off" in blueprint
    assert "dockerContext: ./backend" in blueprint
    assert "dockerfilePath: ./backend/Dockerfile" in blueprint
    assert "mountPath: /app/storage" in blueprint
    assert "healthCheckPath: /health/database" in blueprint
    assert "ipAllowList: []" in blueprint
    assert "property: connectionString" in blueprint
    assert "sync: false" in blueprint
    assert "postgresMajorVersion: \"16\"" in blueprint


def test_api_container_uses_host_provided_port_and_ignores_secrets() -> None:
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    ignore = (ROOT / "backend" / ".dockerignore").read_text(encoding="utf-8")

    assert 'alembic upgrade head && exec uvicorn' in dockerfile
    assert "${PORT:-8000}" in dockerfile
    assert ".env" in ignore
    assert "storage/" in ignore
    assert "*.pdf" in ignore
