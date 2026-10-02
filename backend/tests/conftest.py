import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/ai_document_assistant",
)
os.environ.setdefault("APP_NAME", "Configured Test Assistant")
os.environ.setdefault("LLM_MODEL", "test-generation-model")
