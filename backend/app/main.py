from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import (
    APIException,
    api_exception_handler,
    database_exception_handler,
    http_exception_handler,
    internal_exception_handler,
    validation_exception_handler,
)

from app.api.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.middleware.upload_limit import UploadRequestSizeLimitMiddleware

app = FastAPI(
    title=f"{settings.app_name} API",
    version="0.1.0",
    description="Backend API for an AI-powered document assistant using RAG.",
)

app.add_middleware(UploadRequestSizeLimitMiddleware)
app.add_exception_handler(APIException, api_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, database_exception_handler)
app.add_exception_handler(Exception, internal_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
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
