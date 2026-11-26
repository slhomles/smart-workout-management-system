"""Truy vấn schema `auth` (không chứa nghiệp vụ)."""

import uuid
from datetime import datetime

from sqlalchemy import cast, func, select, update
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import LoginAttempt, RefreshToken, User, UserDevice, UserProfile
from app.models.enums import LoginFailureReason, TokenRevokeReason


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    # email là citext: so sánh không phân biệt hoa thường; bỏ tài khoản đã xoá mềm.
    return await db.scalar(
        select(User).where(User.email == cast(email, CITEXT), User.deleted_at.is_(None))
    )


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))


async def get_profile(db: AsyncSession, user_id: uuid.UUID) -> UserProfile | None:
    return await db.get(UserProfile, user_id)


async def add_login_attempt(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    email: str,
    ip: str | None,
    user_agent: str | None,
    failure_reason: LoginFailureReason | None,
) -> None:
    db.add(
        LoginAttempt(
            user_id=user_id,
            email_attempted=email,
            ip_address=ip,
            user_agent=user_agent,
            succeeded=failure_reason is None,
            failure_reason=failure_reason,
        )
    )
    await db.flush()


async def count_recent_failures(db: AsyncSession, user_id: uuid.UUID, since: datetime) -> int:
    """Số lần sai mật khẩu kể từ `since` và sau lần đăng nhập thành công gần nhất."""
    last_success = (
        select(func.max(LoginAttempt.attempted_at))
        .where(LoginAttempt.user_id == user_id, LoginAttempt.succeeded.is_(True))
        .scalar_subquery()
    )
    return await db.scalar(
        select(func.count())
        .select_from(LoginAttempt)
        .where(
            LoginAttempt.user_id == user_id,
            LoginAttempt.failure_reason == LoginFailureReason.INVALID_CREDENTIALS,
            LoginAttempt.attempted_at >= since,
            LoginAttempt.attempted_at > func.coalesce(last_success, since),
        )
    ) or 0


async def get_active_device(db: AsyncSession, device_id: uuid.UUID, user_id: uuid.UUID) -> UserDevice | None:
    return await db.scalar(
        select(UserDevice).where(
            UserDevice.id == device_id, UserDevice.user_id == user_id, UserDevice.revoked_at.is_(None)
        )
    )


async def get_refresh_token_for_update(db: AsyncSession, token_hash: str) -> RefreshToken | None:
    # Khoá hàng để hai request refresh đồng thời không cùng xoay một token (doc 04 §3.3).
    return await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update())


async def get_user_refresh_token(db: AsyncSession, token_hash: str, user_id: uuid.UUID) -> RefreshToken | None:
    return await db.scalar(
        select(RefreshToken)
        .join(UserDevice, UserDevice.id == RefreshToken.device_id)
        .where(RefreshToken.token_hash == token_hash, UserDevice.user_id == user_id)
        .with_for_update(of=RefreshToken)
    )


async def revoke_family(db: AsyncSession, family_id: uuid.UUID, reason: TokenRevokeReason) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=func.now(), revoke_reason=reason)
    )
