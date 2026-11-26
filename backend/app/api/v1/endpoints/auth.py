"""Endpoint /auth (doc 04 §4). Chỉ nhận request, gọi service, trả kết quả."""

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    RevokedTokensResponse,
    TokenPairResponse,
    UpdateMeRequest,
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

REGISTER_RESPONSES: dict[int | str, dict[str, Any]] = {
    409: {"model": ErrorResponse, "description": "email_already_exists"},
    422: {
        "model": ErrorResponse,
        "description": "validation_error (mật khẩu không đạt chính sách, email sai định dạng, field lạ)",
    },
}

CHANGE_PASSWORD_RESPONSES: dict[int | str, dict[str, Any]] = {
    **ERROR_RESPONSES,
    401: {
        "model": ErrorResponse,
        "description": "invalid_credentials (sai mật khẩu hiện tại) | token_invalid (chưa đăng nhập/token không hợp lệ)",
    },
    422: {
        "model": ErrorResponse,
        "description": "validation_error (mật khẩu mới không đạt chính sách, thiếu field)",
    },
}


UPDATE_ME_RESPONSES: dict[int | str, dict[str, Any]] = {
    **ERROR_RESPONSES,
    401: {"model": ErrorResponse, "description": "token_invalid (chưa đăng nhập/token không hợp lệ)"},
    404: {"model": ErrorResponse, "description": "user_not_found (tài khoản không có hồ sơ)"},
    422: {
        "model": ErrorResponse,
        "description": "validation_error (giá trị sai định dạng, null cho field bắt buộc, múi giờ không tồn tại, field lạ)",
    },
}


def _client(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    user_agent = (request.headers.get("user-agent") or "")[:500] or None
    return ip, user_agent


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=201,
    responses=REGISTER_RESPONSES,
    summary="Đăng ký tài khoản bằng email và mật khẩu",
    description=(
        "Quyền: **công khai**. Tạo tài khoản, hồ sơ và role `user` trong một transaction; không trả token. "
        "Mật khẩu 8–72 byte UTF-8, có chữ cái và chữ số. Email trùng tài khoản chưa xoá → 409 `email_already_exists`."
    ),
)
async def register(body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)) -> RegisterResponse:
    result = await auth_service.register(db, body)
    response.headers["Location"] = f"/api/v1/users/{result.id}"
    return result


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


@router.post(
    "/logout-all",
    response_model=RevokedTokensResponse,
    status_code=200,
    responses=ERROR_RESPONSES,
    summary="Đăng xuất khỏi mọi thiết bị",
    description=(
        "Quyền: **đăng nhập**. Thu hồi mọi refresh token chưa thu hồi trên mọi thiết bị của user (`logout`); "
        "`revoked_count` là số token vừa bị thu hồi. Access token đã cấp còn hiệu lực tới khi hết hạn (tối đa 30 phút)."
    ),
)
async def logout_all(
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RevokedTokensResponse:
    return RevokedTokensResponse(revoked_count=await auth_service.logout_all(db, current.id))


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


@router.patch(
    "/me",
    response_model=MeResponse,
    status_code=200,
    responses=UPDATE_ME_RESPONSES,
    summary="Sửa hồ sơ hiển thị của tài khoản đang đăng nhập",
    description=(
        "Quyền: **đăng nhập**. Sửa một phần `display_name`, `full_name`, `locale`, `timezone`, `unit_system`: "
        "chỉ field có trong body được cập nhật, body rỗng không đổi gì. `full_name: null` xoá họ tên; "
        "các field còn lại không nhận `null`. `timezone` phải là tên IANA có trong `pg_timezone_names`. "
        "Trả thông tin tài khoản sau cập nhật như `GET /auth/me`."
    ),
)
async def update_me(
    body: UpdateMeRequest,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    return await auth_service.update_me(db, current.user, body)


@router.patch(
    "/change-password",
    response_model=MeResponse,
    status_code=200,
    responses=CHANGE_PASSWORD_RESPONSES,
    summary="Đổi mật khẩu",
    description=(
        "Quyền: **đăng nhập**. Sai `current_password` → 401 `invalid_credentials`. Mật khẩu mới 8–72 byte UTF-8, "
        "có chữ cái và chữ số (không đạt → 422 `validation_error`). Thành công: thu hồi mọi refresh token "
        "(`password_changed`), access token cấp trước đó bị từ chối; client phải đăng nhập lại. "
        "Trả thông tin tài khoản như `GET /auth/me`."
    ),
)
async def change_password(
    body: ChangePasswordRequest,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    return await auth_service.change_password(db, current.user, body)
