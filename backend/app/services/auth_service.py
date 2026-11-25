"""
Nghiệp vụ xác thực (doc 04 §3, §4, §6). Endpoint chỉ gọi các hàm ở đây.
Mỗi hàm là một transaction: commit ở cuối, kể cả khi cần ghi login_attempts trước khi báo lỗi.
"""

import math
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppException, UnauthorizedError
from app.core.security import create_access_token, generate_refresh_token, hash_token, verify_password
from app.crud import auth as crud
from app.models.auth import RefreshToken, User, UserDevice
from app.models.enums import LoginFailureReason, TokenRevokeReason, UserStatus
from app.schemas.auth import (
    AuthUserSchema,
    DeviceInfoSchema,
    LoginRequest,
    LoginResponse,
    MeResponse,
    TokenPairResponse,
)
from app.schemas.base import ErrorDetail
from app.services import permission_service

settings = get_settings()


def _account_locked(locked_until: datetime | None, now: datetime) -> AppException:
    details: list[ErrorDetail] = []
    headers = None
    if locked_until and locked_until > now:
        seconds = math.ceil((locked_until - now).total_seconds())
        details = [ErrorDetail(field=None, message=str(seconds), code="retry_after_seconds")]
        headers = {"Retry-After": str(seconds)}
    return AppException(423, "account_locked", "Tài khoản đang bị khoá", details, headers)


async def _db_now(db: AsyncSession) -> datetime:
    return await db.scalar(select(func.now()))


async def _upsert_device(db: AsyncSession, user: User, info: DeviceInfoSchema, now: datetime) -> UserDevice:
    device = await crud.get_active_device(db, info.device_id, user.id) if info.device_id else None
    if device is None:
        device = UserDevice(user_id=user.id, platform=info.platform)
        db.add(device)
    device.platform = info.platform
    device.device_name = info.device_name
    device.os_version = info.os_version
    device.app_version = info.app_version
    device.last_seen_at = now
    if info.push_token is not None and info.push_token != device.push_token:
        device.push_token = info.push_token
        device.push_token_updated_at = now
    await db.flush()
    return device


async def _issue_refresh_token(
    db: AsyncSession,
    *,
    device_id: uuid.UUID,
    family_id: uuid.UUID,
    parent_id: uuid.UUID | None,
    now: datetime,
    ip: str | None,
    user_agent: str | None,
) -> str:
    raw, token_hash = generate_refresh_token()
    db.add(
        RefreshToken(
            device_id=device_id,
            family_id=family_id,
            parent_token_id=parent_id,
            token_hash=token_hash,
            issued_at=now,
            expires_at=now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            ip_address=ip,
            user_agent=user_agent,
        )
    )
    await db.flush()
    return raw


async def login(db: AsyncSession, req: LoginRequest, ip: str | None, user_agent: str | None) -> LoginResponse:
    now = await _db_now(db)
    user = await crud.get_user_by_email(db, req.email)

    async def fail(reason: LoginFailureReason, error: AppException) -> AppException:
        await crud.add_login_attempt(
            db, user_id=user.id if user else None, email=req.email, ip=ip, user_agent=user_agent, failure_reason=reason
        )
        await db.commit()
        return error

    # Khoá tạm vì brute-force: kiểm tra trước để không tốn CPU bcrypt (doc 04 §4.3, §6.2).
    if user and user.locked_until and user.locked_until > now:
        raise await fail(LoginFailureReason.ACCOUNT_LOCKED, _account_locked(user.locked_until, now))

    # Sai email/mật khẩu/không có mật khẩu → cùng một thông báo.
    if not verify_password(req.password, user.password_hash if user else None):
        if user is not None:
            await crud.add_login_attempt(
                db, user_id=user.id, email=req.email, ip=ip, user_agent=user_agent,
                failure_reason=LoginFailureReason.INVALID_CREDENTIALS,
            )
            since = now - timedelta(minutes=settings.LOGIN_FAILURE_WINDOW_MINUTES)
            if await crud.count_recent_failures(db, user.id, since) >= settings.LOGIN_MAX_FAILED_ATTEMPTS:
                user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
            await db.commit()
            raise UnauthorizedError("invalid_credentials", "Email hoặc mật khẩu không đúng")
        raise await fail(
            LoginFailureReason.INVALID_CREDENTIALS,
            UnauthorizedError("invalid_credentials", "Email hoặc mật khẩu không đúng"),
        )

    # Chỉ báo lỗi trạng thái cụ thể sau khi mật khẩu đúng.
    if user.status == UserStatus.DISABLED:
        raise await fail(
            LoginFailureReason.ACCOUNT_DISABLED,
            AppException(403, "account_disabled", "Tài khoản đã bị vô hiệu hoá, vui lòng liên hệ hỗ trợ"),
        )
    if user.status == UserStatus.LOCKED:
        raise await fail(LoginFailureReason.ACCOUNT_LOCKED, _account_locked(user.locked_until, now))
    if user.status == UserStatus.PENDING_VERIFICATION:
        raise await fail(
            LoginFailureReason.EMAIL_NOT_VERIFIED,
            AppException(403, "email_not_verified", "Email chưa được xác thực"),
        )

    await crud.add_login_attempt(db, user_id=user.id, email=req.email, ip=ip, user_agent=user_agent, failure_reason=None)
    device = await _upsert_device(db, user, req.device, now)
    refresh_raw = await _issue_refresh_token(
        db, device_id=device.id, family_id=uuid.uuid4(), parent_id=None, now=now, ip=ip, user_agent=user_agent
    )
    roles = await permission_service.get_role_codes(db, user.id)
    profile = await crud.get_profile(db, user.id)
    await db.commit()

    return LoginResponse(
        access_token=create_access_token(user_id=user.id, roles=roles, device_id=device.id),
        refresh_token=refresh_raw,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        device_id=device.id,
        user=AuthUserSchema(
            id=user.id, email=user.email, display_name=profile.display_name if profile else None, roles=roles
        ),
    )


async def refresh(db: AsyncSession, raw_token: str, ip: str | None, user_agent: str | None) -> TokenPairResponse:
    now = await _db_now(db)
    token = await crud.get_refresh_token_for_update(db, hash_token(raw_token))
    if token is None:
        raise UnauthorizedError("token_invalid", "Refresh token không hợp lệ")

    if token.revoked_at is not None:
        if token.revoke_reason == TokenRevokeReason.ROTATED:
            # Token đã xoay vòng bị gửi lại → nghi bị đánh cắp: thu hồi cả family.
            await crud.revoke_family(db, token.family_id, TokenRevokeReason.REUSE_DETECTED)
            await db.commit()
            raise UnauthorizedError("token_reused", "Phiên đăng nhập không còn an toàn, vui lòng đăng nhập lại")
        raise UnauthorizedError("token_invalid", "Refresh token đã bị thu hồi")

    if token.expires_at <= now:
        raise UnauthorizedError("token_expired", "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại")

    device = await db.get(UserDevice, token.device_id)
    user = await crud.get_user(db, device.user_id) if device else None
    if device is None or device.revoked_at is not None or user is None or user.status != UserStatus.ACTIVE:
        token.revoked_at = now
        token.revoke_reason = (
            TokenRevokeReason.DEVICE_REVOKED if device is None or device.revoked_at else TokenRevokeReason.ADMIN_REVOKED
        )
        await db.commit()
        raise UnauthorizedError("token_invalid", "Phiên đăng nhập không còn hiệu lực")

    token.revoked_at = now
    token.revoke_reason = TokenRevokeReason.ROTATED
    await db.flush()
    new_raw = await _issue_refresh_token(
        db, device_id=device.id, family_id=token.family_id, parent_id=token.id, now=now, ip=ip, user_agent=user_agent
    )
    device.last_seen_at = now
    roles = await permission_service.get_role_codes(db, user.id)
    await db.commit()

    return TokenPairResponse(
        access_token=create_access_token(user_id=user.id, roles=roles, device_id=device.id),
        refresh_token=new_raw,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        device_id=device.id,
    )


async def logout(db: AsyncSession, user_id: uuid.UUID, raw_token: str) -> bool:
    """Idempotent: token không tồn tại / đã thu hồi vẫn thành công (doc 04 §4.5)."""
    token = await crud.get_user_refresh_token(db, hash_token(raw_token), user_id)
    if token is None or token.revoked_at is not None:
        return False
    token.revoked_at = await _db_now(db)
    token.revoke_reason = TokenRevokeReason.LOGOUT
    await db.commit()
    return True


async def get_me(db: AsyncSession, user: User) -> MeResponse:
    profile = await crud.get_profile(db, user.id)
    roles = await permission_service.get_role_codes(db, user.id)
    perms = await permission_service.get_permissions(db, user.id)
    return MeResponse(
        id=user.id,
        email=user.email,
        status=user.status,
        email_verified_at=user.email_verified_at,
        display_name=profile.display_name if profile else None,
        full_name=profile.full_name if profile else None,
        avatar_media_id=profile.avatar_media_id if profile else None,
        locale=profile.locale if profile else None,
        timezone=profile.timezone if profile else None,
        unit_system=profile.unit_system if profile else None,
        roles=roles,
        permissions=sorted(perms),
    )
