"""Endpoint /auth (doc 04 §4). Chỉ nhận request, gọi service, trả kết quả."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    MeResponse,
    RefreshRequest,
    TokenPairResponse,
)
from app.schemas.base import ERROR_RESPONSES, ErrorResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])

LOGIN_RESPONSES = {
    **ERROR_RESPONSES,
    401: {"model": ErrorResponse, "description": "invalid_credentials"},
    403: {"model": ErrorResponse, "description": "account_disabled | email_not_verified"},
    423: {"model": ErrorResponse, "description": "account_locked (details: retry_after_seconds)"},
}


def _client(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    user_agent = (request.headers.get("user-agent") or "")[:500] or None
    return ip, user_agent


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=200,
    responses=LOGIN_RESPONSES,
    summary="Đăng nhập bằng email và mật khẩu",
    description=(
        "Quyền: **công khai**. Tạo/nhận diện thiết bị, trả access token (30 phút) và refresh token (7 ngày). "
        "Mọi lần thử đều được ghi `auth.login_attempts`; sai 5 lần trong 15 phút → khoá 15 phút."
    ),
)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    ip, user_agent = _client(request)
    return await auth_service.login(db, body, ip, user_agent)


@router.post(
    "/refresh",
    response_model=TokenPairResponse,
    status_code=200,
    responses=ERROR_RESPONSES,
    summary="Xoay vòng refresh token",
    description=(
        "Quyền: **công khai** (cần refresh token). Thu hồi token cũ (`rotated`) và cấp cặp token mới. "
        "Gửi lại token đã xoay vòng → `token_reused` và cả family bị thu hồi; hết hạn → `token_expired`."
    ),
)
async def refresh(body: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)) -> TokenPairResponse:
    ip, user_agent = _client(request)
    return await auth_service.refresh(db, body.refresh_token, ip, user_agent)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=200,
    responses=ERROR_RESPONSES,
    summary="Đăng xuất (thu hồi refresh token hiện tại)",
    description="Quyền: **đăng nhập**. Idempotent: token không tồn tại/đã thu hồi vẫn trả 200 với `is_revoked=false`.",
)
async def logout(
    body: LogoutRequest,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LogoutResponse:
    return LogoutResponse(is_revoked=await auth_service.logout(db, current.id, body.refresh_token))


@router.get(
    "/me",
    response_model=MeResponse,
    status_code=200,
    responses=ERROR_RESPONSES,
    summary="Thông tin tài khoản, hồ sơ, vai trò và quyền",
    description="Quyền: **đăng nhập**. `permissions` dạng `resource:action` để frontend ẩn/hiện chức năng.",
)
async def me(current: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> MeResponse:
    return await auth_service.get_me(db, current.user)
