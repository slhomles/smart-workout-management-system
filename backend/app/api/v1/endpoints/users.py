"""Endpoint /users: quản trị người dùng (doc 04 §4.10). Chỉ nhận request, gọi service, trả kết quả."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.models.enums import UserStatus
from app.schemas.base import ERROR_RESPONSES, ErrorResponse, Page
from app.schemas.user import UserAdminOut
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])

READ_USERS = require_permission("user", "read")

USER_READ_RESPONSES: dict[int | str, dict[str, Any]] = {
    **ERROR_RESPONSES,
    401: {
        "model": ErrorResponse,
        "description": "token_invalid | token_expired (chưa đăng nhập/token không hợp lệ)",
    },
    403: {
        "model": ErrorResponse,
        "description": "permission_denied (thiếu quyền `user:read`)",
    },
}

GET_USER_RESPONSES: dict[int | str, dict[str, Any]] = {
    **USER_READ_RESPONSES,
    404: {
        "model": ErrorResponse,
        "description": "user_not_found (không có hoặc đã xoá mềm)",
    },
    422: {
        "model": ErrorResponse,
        "description": "validation_error (`user_id` không phải UUID)",
    },
}

LIST_USERS_RESPONSES: dict[int | str, dict[str, Any]] = {
    **USER_READ_RESPONSES,
    422: {
        "model": ErrorResponse,
        "description": "validation_error (`limit` ngoài 1–100, `cursor` hỏng, `status` sai)",
    },
}


@router.get(
    "",
    response_model=Page[UserAdminOut],
    status_code=200,
    responses=LIST_USERS_RESPONSES,
    summary="Danh sách người dùng (quản trị)",
    description=(
        "Quyền: permission **`user:read`**. Chỉ gồm user chưa xoá mềm, sắp xếp `created_at` giảm dần; "
        "phân trang cursor (`limit` 1–100, mặc định 20; `cursor` lấy từ `next_cursor`). "
        "Lọc tuỳ chọn `status` (`pending_verification`, `active`, `locked`, `disabled`). "
        "`roles` chỉ gồm role còn hiệu lực."
    ),
)
async def list_users(
    status: UserStatus | None = Query(
        None, description="Lọc theo trạng thái tài khoản"
    ),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, description="`next_cursor` của trang trước"),
    _: CurrentUser = Depends(READ_USERS),
    db: AsyncSession = Depends(get_db),
) -> Page[UserAdminOut]:
    return await user_service.list_users(db, status=status, limit=limit, cursor=cursor)


@router.get(
    "/{user_id}",
    response_model=UserAdminOut,
    status_code=200,
    responses=GET_USER_RESPONSES,
    summary="Chi tiết người dùng (quản trị)",
    description=(
        "Quyền: permission **`user:read`**. Trả tài khoản, hồ sơ và role còn hiệu lực của user; "
        "user không tồn tại hoặc đã xoá mềm → 404 `user_not_found`."
    ),
)
async def get_user(
    user_id: uuid.UUID,
    _: CurrentUser = Depends(READ_USERS),
    db: AsyncSession = Depends(get_db),
) -> UserAdminOut:
    return await user_service.get_user(db, user_id)
