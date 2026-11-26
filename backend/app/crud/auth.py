"""Truy vấn schema `auth` (không chứa nghiệp vụ)."""

import uuid
from datetime import datetime

from sqlalchemy import cast, func, literal, select, text, tuple_, update
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import LoginAttempt, RefreshToken, Role, User, UserDevice, UserProfile
from app.models.enums import LoginFailureReason, RoleCode, TokenRevokeReason, UserStatus


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    # email là citext: so sánh không phân biệt hoa thường; bỏ tài khoản đã xoá mềm.
    return await db.scalar(
        select(User).where(User.email == cast(email, CITEXT), User.deleted_at.is_(None))
    )


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))


async def get_profile(db: AsyncSession, user_id: uuid.UUID) -> UserProfile | None:
    return await db.get(UserProfile, user_id)


async def timezone_exists(db: AsyncSession, name: str) -> bool:
    """TRUE nếu `name` là tên múi giờ có trong view hệ thống `pg_catalog.pg_timezone_names` (so khớp chính xác)."""
    found = await db.scalar(
        text("SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_timezone_names WHERE name = :name)"), {"name": name}
    )
    return bool(found)


async def get_role_id(db: AsyncSession, code: RoleCode) -> int | None:
    """Id của role theo `auth.roles.code` (seed 01_rbac.sql); None nếu chưa seed."""
    return await db.scalar(select(Role.id).where(Role.code == code.value))


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


async def revoke_user_tokens(db: AsyncSession, user_id: uuid.UUID, reason: TokenRevokeReason) -> int:
    """
    Thu hồi mọi refresh token chưa thu hồi (kể cả đã quá hạn) trên mọi thiết bị của user; trả số token bị thu hồi.
    `revoked_at` và `revoke_reason` gán cùng lúc (ck_refresh_tokens_revoke).
    """
    result = await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.revoked_at.is_(None),
            RefreshToken.device_id.in_(select(UserDevice.id).where(UserDevice.user_id == user_id)),
        )
        .values(revoked_at=func.now(), revoke_reason=reason)
    )
    return result.rowcount


def _user_with_profile_query():
    # LEFT JOIN: user thiếu `user_profiles` vẫn được trả về, phần hồ sơ là None.
    return (
        select(User, UserProfile)
        .outerjoin(UserProfile, UserProfile.user_id == User.id)
        .where(User.deleted_at.is_(None))
    )


async def list_users_with_profiles(
    db: AsyncSession,
    *,
    status: UserStatus | None,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[tuple[User, UserProfile | None]]:
    """User chưa xoá kèm hồ sơ, sắp xếp `(created_at DESC, id DESC)`, bắt đầu sau vị trí keyset `after`."""
    stmt = _user_with_profile_query()
    if status is not None:
        stmt = stmt.where(User.status == status)
    if after is not None:
        # So sánh cả cặp (created_at, id) vì nhiều user có thể trùng created_at.
        stmt = stmt.where(tuple_(User.created_at, User.id) < tuple_(literal(after[0]), literal(after[1])))
    stmt = stmt.order_by(User.created_at.desc(), User.id.desc()).limit(limit)
    return [(user, profile) for user, profile in (await db.execute(stmt)).tuples()]


async def get_user_with_profile(db: AsyncSession, user_id: uuid.UUID) -> tuple[User, UserProfile | None] | None:
    """User chưa xoá kèm hồ sơ (hồ sơ None nếu chưa có); None nếu không có user hoặc user đã xoá mềm."""
    row = (await db.execute(_user_with_profile_query().where(User.id == user_id))).tuples().first()
    return None if row is None else (row[0], row[1])
