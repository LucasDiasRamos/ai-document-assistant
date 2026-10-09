from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

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
from app.middleware.rate_limit import DemoRateLimitMiddleware
from app.middleware.upload_limit import UploadRequestSizeLimitMiddleware


def health_check() -> dict[str, str]:
    return {"status": "ok"}


def database_health_check() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


def create_app() -> FastAPI:
    production = settings.app_environment == "production"
    application = FastAPI(
        title=f"{settings.app_name} API",
        version="0.1.0",
        description="Backend API for an AI-powered document assistant using RAG.",
        debug=False,
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
    )
    application.add_middleware(UploadRequestSizeLimitMiddleware)
    # Developer tests remain unthrottled; production protects expensive writes.
    if production:
        application.add_middleware(DemoRateLimitMiddleware)

    # Place CORS outermost to include headers on rejections and error responses.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )
    application.add_exception_handler(APIException, api_exception_handler)
    application.add_exception_handler(
        RequestValidationError, validation_exception_handler
    )
    application.add_exception_handler(SQLAlchemyError, database_exception_handler)
    application.add_exception_handler(Exception, internal_exception_handler)
    application.add_exception_handler(
        StarletteHTTPException, http_exception_handler
    )
    application.include_router(api_router)
    application.add_api_route(
        "/health", health_check, methods=["GET"], tags=["Health"]
    )
    application.add_api_route(
        "/health/database",
        database_health_check,
        methods=["GET"],
        tags=["Health"],
    )
    return application


app = create_app()
