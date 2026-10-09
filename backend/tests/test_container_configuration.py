from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_backend_image_bundles_migration_files() -> None:
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(
        encoding="utf-8"
    )
    assert "COPY alembic.ini ." in dockerfile
    assert "COPY alembic ./alembic" in dockerfile
    assert "alembic upgrade head && exec uvicorn" in dockerfile


def test_compose_declares_persistent_storage_and_database_ready_probe() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "condition: service_healthy" in compose
    assert "postgres_data:/var/lib/postgresql/data" in compose
    assert "document_storage:/app/storage" in compose
    assert "STORAGE_ROOT: /app/storage" in compose
    assert "@postgres:5432/" in compose
    assert "/health/database" in compose
