"""Nghiệp vụ quản trị người dùng /users (doc 04 §4.10; spec auth-users quyết định 8, 9)."""

import logging
import uuid
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.crud import auth as crud
from app.models.auth import User, UserProfile
from app.models.enums import RoleCode, UserStatus
from app.schemas.base import Page, build_page, decode_keyset_cursor
from app.schemas.user import UserAdminOut
from app.services import permission_service

logger = logging.getLogger("app.users")

_ADMIN = RoleCode.ADMIN.value


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
    row = await _get_user_row(db, user_id)
    return await _admin_out(db, *row)


async def _get_user_row(
    db: AsyncSession, user_id: uuid.UUID
) -> tuple[User, UserProfile | None]:
    row = await crud.get_user_with_profile(db, user_id)
    if row is None:
        raise NotFoundError("user_not_found", "Người dùng không tồn tại")
    return row


class _RoleChanges(NamedTuple):
    to_add: list[str]
    to_reactivate: list[int]
    to_delete: list[int]


def _plan_role_changes(
    states: list[crud.UserRoleState], wanted: set[str]
) -> _RoleChanges:
    # Role giữ nguyên và còn hiệu lực thì không đụng tới (giữ granted_by, granted_at).
    current_codes = {state.code for state in states}
    return _RoleChanges(
        to_add=sorted(wanted - current_codes),
        to_reactivate=[
            s.role_id for s in states if s.code in wanted and not s.is_active
        ],
        to_delete=[s.role_id for s in states if s.code not in wanted],
    )


def _drops_active_admin(states: list[crud.UserRoleState], wanted: set[str]) -> bool:
    has_active_admin = any(s.code == _ADMIN and s.is_active for s in states)
    return has_active_admin and _ADMIN not in wanted


async def _apply_role_changes(
    db: AsyncSession,
    user_id: uuid.UUID,
    changes: _RoleChanges,
    *,
    granted_by: uuid.UUID,
) -> None:
    if changes.to_delete:
        await crud.delete_user_roles(db, user_id, changes.to_delete)
    if changes.to_reactivate:
        await crud.reactivate_user_roles(
            db, user_id, changes.to_reactivate, granted_by=granted_by
        )
    if changes.to_add:
        role_ids = await crud.get_role_ids(db, changes.to_add)
        # Thiếu role trong seed 01_rbac.sql là lỗi cấu hình → KeyError → 500, không bỏ qua im lặng.
        await crud.add_user_roles(
            db,
            user_id,
            [role_ids[code] for code in changes.to_add],
            granted_by=granted_by,
        )


async def replace_roles(
    db: AsyncSession,
    user_id: uuid.UUID,
    roles: list[RoleCode],
    *,
    actor_id: uuid.UUID,
) -> UserAdminOut:
    """
    Thay thế toàn bộ tập role của user (doc 04 §4.10; spec auth-users quyết định 10).
    User không có/đã xoá → 404 `user_not_found`. Admin tự gỡ `admin` khi là admin hiệu lực cuối cùng
    → 409 `conflict`. Sau commit luôn xoá cache `perm:{user_id}` (doc 04 §2.4).
    """
    user, profile = await _get_user_row(db, user_id)
    states = await crud.list_user_role_states(db, user_id)
    wanted = {role.value for role in roles}
    is_dropping_own_admin = user_id == actor_id and _drops_active_admin(states, wanted)
    if is_dropping_own_admin and not await crud.has_other_active_admin(db, user_id):
        raise ConflictError(
            "conflict", "Không thể tự gỡ role admin khi bạn là admin cuối cùng"
        )
    changes = _plan_role_changes(states, wanted)
    await _apply_role_changes(db, user_id, changes, granted_by=actor_id)
    result = await _admin_out(db, user, profile)
    await db.commit()
    await permission_service.invalidate_permissions(user_id)
    logger.info(
        "admin_action action=replace_roles actor_id=%s target_id=%s roles=%s",
        actor_id,
        user_id,
        ",".join(sorted(wanted)),
    )
    return result
