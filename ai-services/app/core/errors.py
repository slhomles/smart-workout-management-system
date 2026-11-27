"""Lỗi theo một format duy nhất (Claude_api_respone.md §3, 06-ai-contracts.md §2.1).

Endpoint chỉ `raise AppError(...)` hoặc lớp con; handler ở đây dựng body `{"error": {...}}`.
Chỉ dùng mã đã đăng ký ở Claude_api_respone.md §10.
"""

import logging
import secrets

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("ai.errors")
REQUEST_ID_HEADER = "X-Request-ID"


class AppError(Exception):
    """Lỗi nghiệp vụ có mã ổn định; `details` là danh sách {field, message, code}."""

    def __init__(self, status_code: int, code: str, message: str, details: list[dict] | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []


class ServiceUnavailableError(AppError):
    def __init__(self, message: str = "Dịch vụ AI tạm thời không khả dụng") -> None:
        super().__init__(503, "service_unavailable", message)


class BadRequestError(AppError):
    def __init__(self, message: str, details: list[dict] | None = None) -> None:
        super().__init__(400, "bad_request", message, details)


def request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    return rid or request.headers.get(REQUEST_ID_HEADER) or f"req_{secrets.token_hex(4)}"


def error_response(request: Request, error: AppError) -> JSONResponse:
    rid = request_id(request)
    body = {"error": {"code": error.code, "message": error.message, "details": error.details, "request_id": rid}}
    return JSONResponse(status_code=error.status_code, content=body, headers={REQUEST_ID_HEADER: rid})


async def _app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(request, exc)


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = [{"field": ".".join(str(p) for p in err["loc"][1:]) or None, "message": err["msg"], "code": err["type"]}
               for err in exc.errors()]
    return error_response(request, AppError(422, "validation_error", "Dữ liệu gửi lên không hợp lệ", details))


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    return error_response(request, AppError(exc.status_code, f"http_{exc.status_code}", str(exc.detail)))


async def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error on %s", request.url.path)
    return error_response(request, AppError(500, "internal_error", "Lỗi hệ thống, vui lòng thử lại sau"))


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unexpected_error)
