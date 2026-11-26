"""Permission của user dạng `resource:action` (doc 04 §2.4)."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import Permission, Role, RolePermission, UserRole


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


async def get_permissions(db: AsyncSession, user_id: uuid.UUID) -> set[str]:
    """
    Một truy vấn user_roles ⋈ role_permissions ⋈ permissions.
    TODO(core): cache Redis `perm:{user_id}` TTL 5 phút (doc 04 §2.4) khi hạ tầng Redis sẵn sàng.
    """
    rows = await db.execute(
        select(Permission.resource, Permission.action)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id, _active_role_filter())
        .distinct()
    )
    return {f"{resource}:{action}" for resource, action in rows.all()}
