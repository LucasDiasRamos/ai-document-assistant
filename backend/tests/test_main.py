import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/ai_document_assistant",
)
os.environ["APP_NAME"] = "Configured Test Assistant"

from app.main import app


def test_openapi_title_uses_configured_application_name() -> None:
    assert app.title == "Configured Test Assistant API"
