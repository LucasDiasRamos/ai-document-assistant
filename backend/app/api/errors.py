from __future__ import annotations

from enum import StrEnum
import logging

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.observability import log_event


logger = logging.getLogger(__name__)


class APIErrorCode(StrEnum):
    VALIDATION_ERROR = "validation_error"
    UNSUPPORTED_FILE = "unsupported_file"
    UPLOAD_TOO_LARGE = "upload_too_large"
    DOCUMENT_NOT_FOUND = "document_not_found"
    PROCESSING_FAILED = "processing_failed"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    DATABASE_UNAVAILABLE = "database_unavailable"
    INTERNAL_ERROR = "internal_error"
    HTTP_ERROR = "http_error"


class APIException(HTTPException):
    def __init__(
        self,
        *,
        status_code: int,
        code: APIErrorCode,
        detail: str,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


def api_error_response(
    *,
    status_code: int,
    code: APIErrorCode | str,
    detail: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": detail,
            "code": str(code),
        },
    )


async def api_exception_handler(
    request: Request,
    exc: APIException,
) -> JSONResponse:
    log_event(
        logger,
        logging.WARNING if exc.status_code < 500 else logging.ERROR,
        "application.error",
        error_code=str(exc.code),
        http_status=exc.status_code,
        error_type=type(exc).__name__,
    )
    return api_error_response(
        status_code=exc.status_code,
        code=exc.code,
        detail=str(exc.detail),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    log_event(
        logger,
        logging.WARNING,
        "application.error",
        error_code=str(APIErrorCode.VALIDATION_ERROR),
        http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_type=type(exc).__name__,
    )
    return api_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code=APIErrorCode.VALIDATION_ERROR,
        detail="Request validation failed",
    )


async def database_exception_handler(
    request: Request,
    exc: SQLAlchemyError,
) -> JSONResponse:
    log_event(
        logger,
        logging.ERROR,
        "application.error",
        error_code=str(APIErrorCode.DATABASE_UNAVAILABLE),
        http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
        error_type=type(exc).__name__,
    )
    return api_error_response(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code=APIErrorCode.DATABASE_UNAVAILABLE,
        detail="Database is temporarily unavailable",
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    detail = (
        exc.detail
        if isinstance(exc.detail, str)
        else "Request could not be completed"
    )
    log_event(
        logger,
        logging.WARNING if exc.status_code < 500 else logging.ERROR,
        "application.error",
        error_code=str(APIErrorCode.HTTP_ERROR),
        http_status=exc.status_code,
        error_type=type(exc).__name__,
    )
    return api_error_response(
        status_code=exc.status_code,
        code=APIErrorCode.HTTP_ERROR,
        detail=detail,
    )


async def internal_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    log_event(
        logger,
        logging.ERROR,
        "application.error",
        error_code=str(APIErrorCode.INTERNAL_ERROR),
        http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_type=type(exc).__name__,
    )
    return api_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code=APIErrorCode.INTERNAL_ERROR,
        detail="Internal server error",
    )
