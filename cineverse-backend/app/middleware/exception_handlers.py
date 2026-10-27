"""
Centralized exception handlers.

Ensures every error returned by the API has a consistent JSON shape
and that internal stack traces are never leaked to clients.
"""
import uuid

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.config.logging_config import get_logger
from app.exceptions.custom_exceptions import AppException

logger = get_logger(__name__)


def _error_body(error_code: str, message: str, request_id: str, details=None):
    body = {
        "error": {
            "code": error_code,
            "message": message,
            "request_id": request_id,
        }
    }
    if details is not None:
        body["error"]["details"] = details
    return body


def _safe_validation_details(errors: list) -> list:
    """
    Pydantic/FastAPI validation errors can include a raw `input` value
    that is `bytes` (e.g. when validating application/x-www-form-urlencoded
    or multipart bodies). The stdlib json encoder used by JSONResponse
    cannot serialize bytes, which previously caused a 500
    ("Object of type bytes is not JSON serializable") instead of the
    intended 422. jsonable_encoder converts any non-JSON-native types
    (bytes, Decimal, datetime, etc.) into JSON-safe equivalents, with a
    fallback that decodes bytes to a string.
    """
    return jsonable_encoder(
        errors,
        custom_encoder={bytes: lambda b: b.decode("utf-8", errors="replace")},
    )


def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        request_id = str(uuid.uuid4())
        logger.warning(
            "AppException [%s] on %s %s: %s",
            request_id, request.method, request.url.path, exc.message,
        )
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.error_code, exc.message, request_id),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        request_id = str(uuid.uuid4())
        safe_details = _safe_validation_details(exc.errors())
        logger.info(
            "Validation error [%s] on %s %s: %s",
            request_id, request.method, request.url.path, safe_details,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(
                "validation_error",
                "One or more fields failed validation",
                request_id,
                details=safe_details,
            ),
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        request_id = str(uuid.uuid4())
        logger.error(
            "Database error [%s] on %s %s: %s",
            request_id, request.method, request.url.path, str(exc),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                "database_error",
                "A database error occurred. Please try again later.",
                request_id,
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = str(uuid.uuid4())
        logger.exception(
            "Unhandled exception [%s] on %s %s",
            request_id, request.method, request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                "internal_error",
                "An unexpected error occurred. Please try again later.",
                request_id,
            ),
        )
