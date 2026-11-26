"""
Hệ thống lỗi duy nhất của API (Claude_api_respone.md §3, §8; doc 05 §7.4).

Router/service chỉ `raise` các lớp dưới đây; register_exception_handlers() chuyển
mọi lỗi về format {"error": {code, message, details, request_id}}.
Mọi `code` phải có trong Claude_api_respone.md §10.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.base import ErrorBody, ErrorDetail, ErrorResponse

logger = logging.getLogger("app.errors")

_LOCATION_PREFIXES = {"body", "query", "path", "header", "cookie"}


class AppException(Exception):
    """Lỗi nghiệp vụ có status, code ổn định và thông điệp tiếng Việt."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []
        self.headers = headers


class NotFoundError(AppException):
    def __init__(self, code: str = "not_found", message: str = "Không tìm thấy tài nguyên"):
        super().__init__(404, code, message)


class ConflictError(AppException):
    def __init__(self, code: str = "conflict", message: str = "Dữ liệu bị xung đột"):
        super().__init__(409, code, message)


class UnauthorizedError(AppException):
    def __init__(self, code: str = "token_invalid", message: str = "Token không hợp lệ hoặc đã hết hạn"):
        super().__init__(401, code, message, headers={"WWW-Authenticate": "Bearer"})


class PermissionDeniedError(AppException):
    def __init__(self, code: str = "permission_denied", message: str = "Bạn không có quyền thực hiện thao tác này"):
        super().__init__(403, code, message)


class BadRequestError(AppException):
    def __init__(self, code: str = "bad_request", message: str = "Yêu cầu không hợp lệ"):
        super().__init__(400, code, message)


class DataValidationError(AppException):
    """422 validation_error cho lỗi nghiệp vụ/validation tự kiểm tra (không phải Pydantic)."""

    def __init__(self, details: list[ErrorDetail], message: str = "Dữ liệu gửi lên không hợp lệ"):
        super().__init__(422, "validation_error", message, details)


class ServiceUnavailableError(AppException):
    def __init__(self, message: str = "Dịch vụ tạm thời không khả dụng", details: list[ErrorDetail] | None = None):
        super().__init__(503, "service_unavailable", message, details)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _error_json(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, details=details or [], request_id=_request_id(request))
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"), headers=headers)


def _field_path(loc: tuple[Any, ...]) -> str | None:
    parts = list(loc)
    if parts and parts[0] in _LOCATION_PREFIXES:
        parts = parts[1:]
    return ".".join(str(p) for p in parts) or None


def _constraint_name(exc: IntegrityError) -> str:
    cause = getattr(exc.orig, "__cause__", None)
    return getattr(cause, "constraint_name", None) or ""


def register_exception_handlers(app: FastAPI) -> None:
    """Đăng ký handler toàn cục. Không đăng ký handler nào khác format."""

    @app.exception_handler(AppException)
    async def _app_exception(request: Request, exc: AppException) -> JSONResponse:
        return _error_json(request, exc.status_code, exc.code, exc.message, exc.details, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            ErrorDetail(field=_field_path(tuple(e.get("loc", ()))), message=e.get("msg", ""), code=e.get("type", "value_error"))
            for e in exc.errors()
        ]
        return _error_json(request, 422, "validation_error", "Dữ liệu gửi lên không hợp lệ", details)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Lỗi HTTP"
        return _error_json(request, exc.status_code, f"http_{exc.status_code}", message, headers=exc.headers)

    @app.exception_handler(IntegrityError)
    async def _integrity(request: Request, exc: IntegrityError) -> JSONResponse:
        # Dịch vi phạm ràng buộc DB theo tên constraint, không để lộ 500 (doc 05 §3.3, §7.4).
        # Tên constraint/bảng chỉ ghi log server, không trả về client (Claude_api_respone.md §3).
        name = _constraint_name(exc)
        text = str(exc.orig)
        logger.info("integrity_error constraint=%s request_id=%s", name, _request_id(request))
        if name.startswith("ck_") or (name.startswith("fk_") and "is not present" in text):
            detail = ErrorDetail(field=None, message="Giá trị vi phạm ràng buộc dữ liệu", code="constraint_violation")
            return _error_json(request, 422, "validation_error", "Dữ liệu gửi lên không hợp lệ", [detail])
        return _error_json(request, 409, "conflict", "Dữ liệu bị xung đột")

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_error request_id=%s", _request_id(request), exc_info=exc)
        return _error_json(request, 500, "internal_error", "Lỗi hệ thống, vui lòng thử lại sau")
