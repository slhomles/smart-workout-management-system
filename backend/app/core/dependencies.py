"""
Dependency xác thực & phân quyền (doc 04 §8.3).

- Depends(get_current_user): yêu cầu đăng nhập.
- Depends(require_permission("body_metric", "manage_own")): yêu cầu permission.
- Depends(verify_worker_token): route worker video, xác thực header X-Worker-Token (06-ai-contracts §3.1).
Dùng HTTPBearer (không dùng OAuth2PasswordBearer) vì /auth/login nhận JSON.
"""

import hmac
import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import PermissionDeniedError, UnauthorizedError
from app.core.security import decode_access_token
from app.models.auth import User
from app.models.enums import UserStatus
from app.services import permission_service

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    """User đang đăng nhập + thiết bị lấy từ claim `did` của access token."""

    user: User
    device_id: uuid.UUID

    @property
    def id(self) -> uuid.UUID:
        return self.user.id


async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    if creds is None:
        raise UnauthorizedError("token_invalid", "Thiếu access token")
    payload = decode_access_token(creds.credentials)
    try:
        user_id = uuid.UUID(payload["sub"])
        device_id = uuid.UUID(payload["did"])
    except (ValueError, TypeError):
        raise UnauthorizedError("token_invalid", "Token không hợp lệ") from None

    user = await db.scalar(
        select(User).where(User.id == user_id, User.deleted_at.is_(None), User.status == UserStatus.ACTIVE)
    )
    if user is None:
        raise UnauthorizedError("token_invalid", "Tài khoản không khả dụng")
    if user.password_changed_at and int(payload.get("iat", 0)) < int(user.password_changed_at.timestamp()):
        raise UnauthorizedError("token_invalid", "Token cấp trước khi đổi mật khẩu")

    request.state.user_id = str(user.id)
    return CurrentUser(user=user, device_id=device_id)


def require_permission(resource: str, action: str):
    """Server quyết định bằng permission, không dựa vào claim `roles` (doc 04 §2.4)."""

    async def checker(
        current: CurrentUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> CurrentUser:
        perms = await permission_service.get_permissions(db, current.id)
        if f"{resource}:{action}" not in perms:
            raise PermissionDeniedError()
        return current

    return checker


async def verify_worker_token(x_worker_token: str | None = Header(None, alias="X-Worker-Token")) -> None:
    """Xác thực worker video bằng bí mật chung AI_WORKER_TOKEN (06-ai-contracts §3.1).

    Worker không có user nên không dùng JWT/RBAC. Đọc cấu hình lúc chạy request để test monkeypatch được.
    So sánh bằng bytes qua hmac.compare_digest: thời gian hằng, và header không phải ASCII không gây TypeError.
    Không log giá trị token hay header.
    """
    expected = get_settings().AI_WORKER_TOKEN
    if not expected or x_worker_token is None:
        raise UnauthorizedError("unauthorized", "Worker token không hợp lệ")
    if not hmac.compare_digest(x_worker_token.encode("utf-8"), expected.encode("utf-8")):
        raise UnauthorizedError("unauthorized", "Worker token không hợp lệ")
