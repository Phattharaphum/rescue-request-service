from typing import Any


class AppError(Exception):
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, details: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or []


class BadRequestError(AppError):
    status_code = 400
    error_code = "BAD_REQUEST"


class ValidationError(AppError):
    status_code = 422
    error_code = "VALIDATION_ERROR"


class UnauthorizedError(AppError):
    status_code = 401
    error_code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    status_code = 403
    error_code = "FORBIDDEN"


class NotFoundError(AppError):
    status_code = 404
    error_code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    error_code = "CONFLICT"


class TooManyRequestsError(AppError):
    status_code = 429
    error_code = "TOO_MANY_REQUESTS"


class ServiceUnavailableError(AppError):
    status_code = 503
    error_code = "SERVICE_UNAVAILABLE"
