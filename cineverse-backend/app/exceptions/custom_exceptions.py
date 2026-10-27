"""
Custom application exception hierarchy.

Services and repositories raise these instead of returning HTTP
responses directly. The centralized exception handlers (see
app/middleware/exception_handlers.py) translate them into proper
JSON error responses.
"""


class AppException(Exception):
    """Base class for all application-level exceptions."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str = "An unexpected error occurred", retry_after: int | None = None):
        self.message = message
        # Optional seconds-until-retry, surfaced as a Retry-After header
        # by the generic exception handler (see
        # app/middleware/exception_handlers.py). None for every
        # existing exception type -- only RateLimitExceededException
        # sets this, so no other exception's behavior changes.
        self.retry_after = retry_after
        super().__init__(message)


class NotFoundException(AppException):
    status_code = 404
    error_code = "not_found"

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message)


class ConflictException(AppException):
    status_code = 409
    error_code = "conflict"

    def __init__(self, message: str = "Resource conflict"):
        super().__init__(message)


class ValidationException(AppException):
    status_code = 422
    error_code = "validation_error"

    def __init__(self, message: str = "Validation failed"):
        super().__init__(message)


class UnauthorizedException(AppException):
    status_code = 401
    error_code = "unauthorized"

    def __init__(self, message: str = "Not authenticated"):
        super().__init__(message)


class ForbiddenException(AppException):
    status_code = 403
    error_code = "forbidden"

    def __init__(self, message: str = "Not authorized to perform this action"):
        super().__init__(message)


class InvalidStateTransitionException(ConflictException):
    error_code = "invalid_state_transition"

    def __init__(self, current_state: str, target_state: str):
        message = (
            f"Cannot transition subscription from '{current_state}' "
            f"to '{target_state}'"
        )
        super().__init__(message)


class RateLimitExceededException(AppException):
    status_code = 429
    error_code = "rate_limit_exceeded"

    def __init__(self, message: str = "Too many requests. Please try again later.", retry_after: int = 60):
        super().__init__(message, retry_after=retry_after)
