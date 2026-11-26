"""Permission của user dạng `resource:action` (doc 04 §2.4)."""

import json
import logging
import uuid

from redis.exceptions import RedisError
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis_client import get_redis
from app.models.auth import Permission, Role, RolePermission, UserRole

logger = logging.getLogger("app.permissions")


def cache_key(user_id: uuid.UUID) -> str:
    return f"perm:{user_id}"


def _active_role_filter():
    # Vai trò đã hết hạn PHẢI bị bỏ qua (doc 04 §2.1).
    return or_(UserRole.expires_at.is_(None), UserRole.expires_at > func.now())


async def get_role_codes(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    rows = await db.execute(
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id, _active_role_filter())
        .order_by(Role.code)
    )
    return list(rows.scalars())


async def _load_permissions(db: AsyncSession, user_id: uuid.UUID) -> set[str]:
    """Một truy vấn user_roles ⋈ role_permissions ⋈ permissions, đã loại role hết hạn."""
    rows = await db.execute(
        select(Permission.resource, Permission.action)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id, _active_role_filter())
        .distinct()
    )
    return {f"{resource}:{action}" for resource, action in rows.all()}


async def get_permissions(db: AsyncSession, user_id: uuid.UUID) -> set[str]:
    """
    Cache Redis `perm:{user_id}` (JSON list `resource:action`, TTL PERMISSION_CACHE_TTL_SECONDS).
    Cache miss hoặc Redis lỗi → đọc DB: mất Redis không được làm hỏng xác thực.
    """
    key = cache_key(user_id)
    try:
        cached = await get_redis().get(key)
        if cached is not None:
            return set(json.loads(cached))
    except (RedisError, OSError, ValueError):
        logger.warning("permission cache read failed", exc_info=True)

    permissions = await _load_permissions(db, user_id)
    try:
        await get_redis().set(key, json.dumps(sorted(permissions)), ex=get_settings().PERMISSION_CACHE_TTL_SECONDS)
    except (RedisError, OSError):
        logger.warning("permission cache write failed", exc_info=True)
    return permissions


async def invalidate_permissions(user_id: uuid.UUID) -> None:
    """Xoá cache khi gán/thu hồi role (doc 04 §2.4). Lỗi Redis chỉ ghi log: cache tự hết hạn sau TTL."""
    try:
        await get_redis().delete(cache_key(user_id))
    except (RedisError, OSError):
        logger.warning("permission cache invalidate failed", exc_info=True)
