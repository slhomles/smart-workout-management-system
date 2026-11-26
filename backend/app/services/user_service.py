"""Nghiệp vụ quản trị người dùng /users (doc 04 §4.10; spec auth-users quyết định 8, 9)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.crud import auth as crud
from app.models.auth import User, UserProfile
from app.models.enums import UserStatus
from app.schemas.base import Page, build_page, decode_keyset_cursor
from app.schemas.user import UserAdminOut
from app.services import permission_service


def _to_admin_out(
    user: User, profile: UserProfile | None, roles: list[str]
) -> UserAdminOut:
    return UserAdminOut(
        id=user.id,
        email=user.email,
        status=user.status,
        email_verified_at=user.email_verified_at,
        locked_until=user.locked_until,
        display_name=profile.display_name if profile else None,
        full_name=profile.full_name if profile else None,
        locale=profile.locale if profile else None,
        timezone=profile.timezone if profile else None,
        unit_system=profile.unit_system if profile else None,
        roles=roles,
        created_at=user.created_at,
    )


async def _admin_out(
    db: AsyncSession, user: User, profile: UserProfile | None
) -> UserAdminOut:
    # get_role_codes đã bỏ role hết hạn và sắp xếp tăng dần (doc 04 §2.1).
    return _to_admin_out(
        user, profile, await permission_service.get_role_codes(db, user.id)
    )


async def list_users(
    db: AsyncSession, *, status: UserStatus | None, limit: int, cursor: str | None
) -> Page[UserAdminOut]:
    """
    Danh sách user chưa xoá mềm, keyset `(created_at DESC, id DESC)`; lấy `limit + 1` dòng để biết `has_more`.
    Cursor hỏng → 422 `validation_error` (field `cursor`).
    """
    after = decode_keyset_cursor(cursor, "created_at")
    rows = await crud.list_users_with_profiles(
        db, status=status, after=after, limit=limit + 1
    )
    items = {
        user.id: await _admin_out(db, user, profile) for user, profile in rows[:limit]
    }
    return build_page(
        rows,
        limit,
        to_item=lambda row: items[row[0].id],
        cursor_of=lambda row: {
            "created_at": row[0].created_at.isoformat(),
            "id": str(row[0].id),
        },
    )


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> UserAdminOut:
    """Chi tiết một user chưa xoá mềm; không có hoặc đã xoá → 404 `user_not_found`."""
    row = await crud.get_user_with_profile(db, user_id)
    if row is None:
        raise NotFoundError("user_not_found", "Người dùng không tồn tại")
    return await _admin_out(db, *row)
