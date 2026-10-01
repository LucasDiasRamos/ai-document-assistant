from fastapi import FastAPI
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import settings
from app.core.database import engine

app = FastAPI(
    title=f"{settings.app_name} API",
    version="0.1.0",
    description="Backend API for an AI-powered document assistant using RAG.",
)

app.include_router(api_router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/database", tags=["Health"])
def database_health_check() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return {
        "status": "ok",
        "database": "connected",
    }
