"""
Schema dùng chung cho mọi endpoint (Claude_api_respone.md §3, §5).

- ErrorResponse: format lỗi duy nhất {"error": {code, message, details, request_id}}.
- Page[T]: danh sách {"data": [...], "pagination": {next_cursor, has_more}}.
- encode_cursor / decode_cursor: cursor mờ (base64url của JSON); client không tự tạo.
"""

import base64
import binascii
import json
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    field: str | None = Field(None, description="Đường dẫn field lỗi, vd 'email', 'address.city'")
    message: str
    code: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class Pagination(BaseModel):
    next_cursor: str | None = None
    has_more: bool = False


class Page(BaseModel, Generic[T]):
    data: list[T]
    pagination: Pagination


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Chưa đăng nhập / token không hợp lệ"},
    403: {"model": ErrorResponse, "description": "Không đủ quyền"},
    404: {"model": ErrorResponse, "description": "Không tìm thấy"},
    409: {"model": ErrorResponse, "description": "Xung đột dữ liệu"},
    422: {"model": ErrorResponse, "description": "Dữ liệu không hợp lệ"},
}


def encode_cursor(values: dict[str, Any]) -> str:
    """Mã hoá vị trí trang tiếp theo thành chuỗi mờ."""
    raw = json.dumps(values, separators=(",", ":"), default=str).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> dict[str, Any]:
    """Giải mã cursor; cursor hỏng → 422 validation_error (field 'cursor')."""
    from app.core.exceptions import DataValidationError

    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, binascii.Error, UnicodeError):
        raise DataValidationError(
            [ErrorDetail(field="cursor", message="Cursor không hợp lệ", code="invalid_cursor")]
        ) from None


def decode_keyset_cursor(cursor: str | None, key: str) -> tuple[datetime, uuid.UUID] | None:
    """Giải mã cursor dạng {key: <ISO datetime>, "id": <uuid>} cho sắp xếp (key DESC, id DESC)."""
    from app.core.exceptions import DataValidationError

    if cursor is None:
        return None
    values = decode_cursor(cursor)
    try:
        return datetime.fromisoformat(values[key]), uuid.UUID(values["id"])
    except (KeyError, ValueError, TypeError):
        raise DataValidationError(
            [ErrorDetail(field="cursor", message="Cursor không hợp lệ", code="invalid_cursor")]
        ) from None


def build_page(
    rows: Sequence[Any],
    limit: int,
    to_item: Callable[[Any], T],
    cursor_of: Callable[[Any], dict[str, Any]],
) -> Page[T]:
    """Dựng Page[T] từ `limit + 1` bản ghi đã sắp xếp (không dùng COUNT(*))."""
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(cursor_of(rows[-1])) if has_more and rows else None
    return Page[T](
        data=[to_item(r) for r in rows],
        pagination=Pagination(next_cursor=next_cursor, has_more=has_more),
    )
