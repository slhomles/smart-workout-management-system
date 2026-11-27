"""Integration test /users (quản trị người dùng) trên PostgreSQL thật (persona seed, docs/database/test-dataset.md)."""

import hashlib
import itertools
import uuid
from collections.abc import AsyncGenerator, Collection
from datetime import datetime
from typing import NamedTuple

import pytest
import pytest_asyncio
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.models.auth import RefreshToken, Role, User, UserDevice, UserProfile, UserRole
from app.models.enums import TokenRevokeReason, UserStatus
from app.services.permission_service import cache_key
from tests.conftest import SEED_PASSWORD, persona_id

USERS = "/api/v1/users"
ADMIN_OUT_KEYS = {
    "id",
    "email",
    "status",
    "email_verified_at",
    "locked_until",
    "display_name",
    "full_name",
    "locale",
    "timezone",
    "unit_system",
    "roles",
    "created_at",
}
MAX_PAGES = 100  # chặn vòng lặp vô hạn nếu cursor hỏng


def _assert_error(res, status: int, code: str) -> dict:
    assert res.status_code == status, res.text
    body = res.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["details"], list)
    assert body["error"]["request_id"] == res.headers["X-Request-ID"]
    return body["error"]


async def _alive_user_ids(
    db: AsyncSession, status: UserStatus | None = None
) -> set[str]:
    stmt = select(User.id).where(User.deleted_at.is_(None))
    if status is not None:
        stmt = stmt.where(User.status == status)
    return {str(user_id) for user_id in await db.scalars(stmt)}


def _sort_key(item: dict) -> tuple[datetime, uuid.UUID]:
    return datetime.fromisoformat(item["created_at"]), uuid.UUID(item["id"])


def _assert_sorted_desc(items: list[dict]) -> None:
    keys = [_sort_key(item) for item in items]
    assert keys == sorted(keys, reverse=True)


async def _fetch_all_pages(
    client: AsyncClient, headers: dict[str, str], limit: int
) -> list[dict]:
    pages: list[dict] = []
    params: dict[str, str | int] = {"limit": limit}
    for _ in range(MAX_PAGES):
        res = await client.get(USERS, params=params, headers=headers)
        assert res.status_code == 200, res.text
        pages.append(res.json())
        pagination = pages[-1]["pagination"]
        if not pagination["has_more"]:
            return pages
        params = {"limit": limit, "cursor": pagination["next_cursor"]}
    raise AssertionError(f"Phân trang không kết thúc sau {MAX_PAGES} trang")


# --- GET /users ---
@pytest.mark.tc("AUTH-16")
async def test_list_users_default_returns_first_page_sorted_desc(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    alive_ids = await _alive_user_ids(db)
    res = await client.get(USERS, headers=await auth_headers("admin"))
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == {"data", "pagination"}
    data = body["data"]
    assert len(data) == min(20, len(alive_ids))
    assert persona_id(14) not in {item["id"] for item in data}
    assert all(set(item) == ADMIN_OUT_KEYS for item in data)
    _assert_sorted_desc(data)
    assert body["pagination"]["has_more"] is (len(alive_ids) > 20)


@pytest.mark.tc("AUTH-16")
async def test_list_users_follow_cursor_returns_every_alive_user_once(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    alive_ids = await _alive_user_ids(db)
    pages = await _fetch_all_pages(client, await auth_headers("admin"), limit=5)
    assert all(len(page["data"]) <= 5 for page in pages)
    assert pages[-1]["pagination"] == {"next_cursor": None, "has_more": False}
    items = [item for page in pages for item in page["data"]]
    ids = [item["id"] for item in items]
    assert len(ids) == len(set(ids)) == len(alive_ids)
    assert set(ids) == alive_ids
    assert persona_id(14) not in ids
    _assert_sorted_desc(items)


@pytest.mark.tc("AUTH-16")
async def test_list_users_filter_locked_returns_only_locked(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    locked_ids = await _alive_user_ids(db, UserStatus.LOCKED)
    res = await client.get(
        USERS, params={"status": "locked"}, headers=await auth_headers("admin")
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data
    assert all(item["status"] == "locked" for item in data)
    assert persona_id(12) in {item["id"] for item in data}
    assert {item["id"] for item in data} == locked_ids


@pytest.mark.tc("AUTH-17")
@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"limit": 0}, "limit"),
        ({"limit": 101}, "limit"),
        ({"cursor": "!!!khong-phai-cursor"}, "cursor"),
        ({"status": "premium"}, "status"),
    ],
)
async def test_list_users_invalid_query_returns_validation_error(
    client: AsyncClient, auth_headers, params: dict, field: str
):
    res = await client.get(USERS, params=params, headers=await auth_headers("admin"))
    error = _assert_error(res, 422, "validation_error")
    assert field in {detail["field"] for detail in error["details"]}


async def test_list_users_as_regular_user_returns_permission_denied(
    client: AsyncClient, auth_headers
):
    res = await client.get(USERS, headers=await auth_headers("demo"))
    _assert_error(res, 403, "permission_denied")


async def test_list_users_without_token_returns_token_invalid(client: AsyncClient):
    res = await client.get(USERS)
    _assert_error(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"


# --- GET /users/{user_id} ---
@pytest.mark.tc("AUTH-18")
async def test_get_user_demo_returns_admin_out(client: AsyncClient, auth_headers):
    res = await client.get(
        f"{USERS}/{persona_id(3)}", headers=await auth_headers("admin")
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == ADMIN_OUT_KEYS
    assert body["id"] == persona_id(3)
    assert body["email"] == "demo@smartworkout.local"
    assert body["roles"] == ["user"]
    assert body["display_name"] == "An"
    assert body["full_name"] == "Nguyễn Văn An"
    assert body["status"] == "active"


@pytest.mark.tc("AUTH-18")
async def test_get_user_with_expired_role_ignores_expired_role(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    trainer_id = uuid.UUID(persona_id(16))
    # Seed: trainer còn dòng content_editor đã hết hạn; API phải bỏ qua dòng này.
    expired_codes = await db.scalars(
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == trainer_id, UserRole.expires_at.is_not(None))
    )
    assert "content_editor" in set(expired_codes)
    res = await client.get(f"{USERS}/{trainer_id}", headers=await auth_headers("admin"))
    assert res.status_code == 200, res.text
    assert res.json()["roles"] == ["user"]


@pytest.mark.tc("AUTH-18")
@pytest.mark.parametrize(
    "user_id", [persona_id(14), str(uuid.uuid4())], ids=["soft_deleted", "random_uuid"]
)
async def test_get_user_deleted_or_unknown_returns_not_found(
    client: AsyncClient, auth_headers, user_id: str
):
    res = await client.get(f"{USERS}/{user_id}", headers=await auth_headers("admin"))
    _assert_error(res, 404, "user_not_found")


@pytest.mark.tc("AUTH-18")
async def test_get_user_malformed_id_returns_validation_error(
    client: AsyncClient, auth_headers
):
    res = await client.get(f"{USERS}/abc", headers=await auth_headers("admin"))
    error = _assert_error(res, 422, "validation_error")
    assert "user_id" in {detail["field"] for detail in error["details"]}


async def test_get_user_as_regular_user_returns_permission_denied(
    client: AsyncClient, auth_headers
):
    res = await client.get(
        f"{USERS}/{persona_id(3)}", headers=await auth_headers("demo")
    )
    _assert_error(res, 403, "permission_denied")


async def test_get_user_without_token_returns_token_invalid(client: AsyncClient):
    res = await client.get(f"{USERS}/{persona_id(3)}")
    _assert_error(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"


# --- PUT /users/{user_id}/roles ---
RoleRow = tuple[uuid.UUID | None, datetime, datetime | None]
EDITOR_AND_USER = {"roles": ["user", "content_editor"]}
# Persona có thể bị đổi role hoặc bị đọc quyền trong các test PUT roles.
CACHE_TOUCHED_PERSONAS = (1, 2, 3, 8, 14, 16)


def _roles_url(user_id: str) -> str:
    return f"{USERS}/{user_id}/roles"


@pytest_asyncio.fixture
async def perm_cache() -> AsyncGenerator[Redis, None]:
    """
    Redis thật dùng chung, còn DB thì rollback: xoá `perm:<uuid>` của persona bị chạm sau test
    để cache không giữ quyền của dữ liệu đã rollback (spec auth-users quyết định 13). Không FLUSHDB.
    """
    redis = get_redis()
    keys = [cache_key(uuid.UUID(persona_id(nn))) for nn in CACHE_TOUCHED_PERSONAS]
    try:
        yield redis
    finally:
        await redis.delete(*keys)


async def _role_rows(db: AsyncSession, user_id: str) -> dict[str, RoleRow]:
    """Mọi dòng user_roles của user (kể cả hết hạn), đọc thẳng cột từ DB."""
    rows = await db.execute(
        select(Role.code, UserRole.granted_by, UserRole.granted_at, UserRole.expires_at)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == uuid.UUID(user_id))
    )
    return {
        code: (granted_by, granted_at, expires_at)
        for code, granted_by, granted_at, expires_at in rows.tuples()
    }


async def _active_role_codes(db: AsyncSession, user_id: str) -> set[str]:
    codes = await db.scalars(
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == uuid.UUID(user_id),
            UserRole.expires_at.is_(None) | (UserRole.expires_at > func.now()),
        )
    )
    return set(codes)


def _assert_granted_by_admin(row: RoleRow) -> None:
    granted_by, _, expires_at = row
    assert granted_by == uuid.UUID(persona_id(1))
    assert expires_at is None


async def _put_roles(
    client: AsyncClient, headers: dict[str, str], user_id: str, body: dict
):
    return await client.put(_roles_url(user_id), json=body, headers=headers)


@pytest.mark.tc("AUTH-19")
async def test_replace_roles_add_editor_returns_admin_out_and_clears_cache(
    client: AsyncClient, db: AsyncSession, auth_headers, perm_cache: Redis
):
    newbie = persona_id(8)
    key = cache_key(uuid.UUID(newbie))
    await perm_cache.set(key, "[]")
    user_row_before = (await _role_rows(db, newbie))["user"]

    res = await _put_roles(client, await auth_headers("admin"), newbie, EDITOR_AND_USER)
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == ADMIN_OUT_KEYS
    assert body["id"] == newbie
    assert body["roles"] == ["content_editor", "user"]
    assert await perm_cache.exists(key) == 0

    rows = await _role_rows(db, newbie)
    assert set(rows) == {"content_editor", "user"}
    _assert_granted_by_admin(rows["content_editor"])
    # Role giữ nguyên thì giữ nguyên dòng (granted_by, granted_at): spec quyết định 10.
    assert rows["user"] == user_row_before


@pytest.mark.tc("AUTH-19")
async def test_replace_roles_add_editor_then_me_has_editor_permission(
    client: AsyncClient, auth_headers, perm_cache: Redis
):
    newbie = persona_id(8)
    await perm_cache.set(cache_key(uuid.UUID(newbie)), "[]")
    res = await _put_roles(client, await auth_headers("admin"), newbie, EDITOR_AND_USER)
    assert res.status_code == 200, res.text

    me = await client.get("/api/v1/auth/me", headers=await auth_headers("newbie"))
    assert me.status_code == 200, me.text
    assert "exercise:create" in me.json()["permissions"]
    assert me.json()["roles"] == ["content_editor", "user"]


@pytest.mark.tc("AUTH-19")
async def test_replace_roles_expired_role_reactivates_existing_row(
    client: AsyncClient, db: AsyncSession, auth_headers, perm_cache: Redis
):
    trainer = persona_id(16)
    assert (await _role_rows(db, trainer))["content_editor"][2] is not None

    res = await _put_roles(client, await auth_headers("admin"), trainer, EDITOR_AND_USER)
    assert res.status_code == 200, res.text
    assert res.json()["roles"] == ["content_editor", "user"]

    rows = await _role_rows(db, trainer)
    assert set(rows) == {"content_editor", "user"}
    _assert_granted_by_admin(rows["content_editor"])
    assert await perm_cache.exists(cache_key(uuid.UUID(trainer))) == 0


@pytest.mark.tc("AUTH-19")
async def test_replace_roles_repeated_same_body_returns_same_result(
    client: AsyncClient, db: AsyncSession, auth_headers, perm_cache: Redis
):
    newbie = persona_id(8)
    headers = await auth_headers("admin")
    first = await _put_roles(client, headers, newbie, EDITOR_AND_USER)
    assert first.status_code == 200, first.text
    rows_after_first = await _role_rows(db, newbie)

    second = await _put_roles(client, headers, newbie, EDITOR_AND_USER)
    assert second.status_code == 200, second.text
    assert second.json() == first.json()
    assert await _role_rows(db, newbie) == rows_after_first
    assert len(rows_after_first) == 2


@pytest.mark.tc("AUTH-20")
@pytest.mark.parametrize(
    "body",
    [{"roles": ["content_editor"]}, {"roles": ["premium"]}, {"roles": []}],
    ids=["missing_user", "unknown_role", "empty"],
)
@pytest.mark.usefixtures("perm_cache")
async def test_replace_roles_invalid_body_returns_validation_error(
    client: AsyncClient, db: AsyncSession, auth_headers, body: dict
):
    newbie = persona_id(8)
    rows_before = await _role_rows(db, newbie)
    res = await _put_roles(client, await auth_headers("admin"), newbie, body)
    error = _assert_error(res, 422, "validation_error")
    fields = [detail["field"] or "" for detail in error["details"]]
    assert fields
    assert all(field.startswith("roles") for field in fields)
    assert await _role_rows(db, newbie) == rows_before


@pytest.mark.tc("AUTH-20")
async def test_replace_roles_soft_deleted_user_returns_not_found(
    client: AsyncClient, db: AsyncSession, auth_headers, perm_cache: Redis
):
    deleted = persona_id(14)
    rows_before = await _role_rows(db, deleted)
    res = await _put_roles(client, await auth_headers("admin"), deleted, EDITOR_AND_USER)
    _assert_error(res, 404, "user_not_found")
    assert await _role_rows(db, deleted) == rows_before


async def test_replace_roles_unknown_user_returns_not_found(
    client: AsyncClient, auth_headers, perm_cache: Redis
):
    res = await _put_roles(
        client, await auth_headers("admin"), str(uuid.uuid4()), EDITOR_AND_USER
    )
    _assert_error(res, 404, "user_not_found")


@pytest.mark.tc("AUTH-20")
async def test_replace_roles_last_admin_removes_own_admin_returns_conflict(
    client: AsyncClient, db: AsyncSession, auth_headers, perm_cache: Redis
):
    admin = persona_id(1)
    rows_before = await _role_rows(db, admin)
    res = await _put_roles(client, await auth_headers("admin"), admin, {"roles": ["user"]})
    _assert_error(res, 409, "conflict")
    assert "admin" in await _active_role_codes(db, admin)
    rows_after = await _role_rows(db, admin)
    assert "user" not in rows_after
    assert rows_after == rows_before


async def test_replace_roles_drop_editor_deletes_role_row(
    client: AsyncClient, db: AsyncSession, auth_headers, perm_cache: Redis
):
    editor = persona_id(2)
    res = await _put_roles(client, await auth_headers("admin"), editor, {"roles": ["user"]})
    assert res.status_code == 200, res.text
    assert res.json()["roles"] == ["user"]
    rows = await _role_rows(db, editor)
    assert set(rows) == {"user"}
    _assert_granted_by_admin(rows["user"])


async def test_replace_roles_duplicate_codes_are_deduplicated(
    client: AsyncClient, db: AsyncSession, auth_headers, perm_cache: Redis
):
    newbie = persona_id(8)
    body = {"roles": ["user", "content_editor", "user", "content_editor"]}
    res = await _put_roles(client, await auth_headers("admin"), newbie, body)
    assert res.status_code == 200, res.text
    assert res.json()["roles"] == ["content_editor", "user"]
    assert set(await _role_rows(db, newbie)) == {"content_editor", "user"}


async def test_replace_roles_as_regular_user_returns_permission_denied(
    client: AsyncClient, db: AsyncSession, auth_headers, perm_cache: Redis
):
    demo = persona_id(3)
    rows_before = await _role_rows(db, demo)
    res = await _put_roles(client, await auth_headers("demo"), demo, EDITOR_AND_USER)
    _assert_error(res, 403, "permission_denied")
    assert await _role_rows(db, demo) == rows_before


async def test_replace_roles_without_token_returns_token_invalid(client: AsyncClient):
    res = await client.put(_roles_url(persona_id(3)), json=EDITOR_AND_USER)
    _assert_error(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"


# --- POST /users/{user_id}/lock, /users/{user_id}/unlock ---
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
ME = "/api/v1/auth/me"
DEMO_REFRESH = "seed-refresh-demo-2"
UserState = tuple[UserStatus, datetime | None]


def _action_url(user_id: str, action: str) -> str:
    return f"{USERS}/{user_id}/{action}"


async def _login(client: AsyncClient, email: str):
    return await client.post(
        LOGIN,
        json={"email": email, "password": SEED_PASSWORD, "device": {"platform": "web"}},
    )


async def _user_state(db: AsyncSession, user_id: str) -> UserState:
    """(status, locked_until) đọc thẳng cột từ `auth.users`, không qua identity map."""
    row = (
        await db.execute(
            select(User.status, User.locked_until).where(User.id == uuid.UUID(user_id))
        )
    ).one()
    return row.status, row.locked_until


async def _unrevoked_token_ids(db: AsyncSession, user_id: str) -> set[uuid.UUID]:
    """Id refresh token chưa thu hồi trên mọi thiết bị của user."""
    ids = await db.scalars(
        select(RefreshToken.id)
        .join(UserDevice, UserDevice.id == RefreshToken.device_id)
        .where(
            UserDevice.user_id == uuid.UUID(user_id), RefreshToken.revoked_at.is_(None)
        )
    )
    return set(ids)


async def _revocations(
    db: AsyncSession, token_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, tuple[datetime | None, TokenRevokeReason | None]]:
    """id → (revoked_at, revoke_reason) của các refresh token theo id."""
    rows = await db.execute(
        select(RefreshToken.id, RefreshToken.revoked_at, RefreshToken.revoke_reason).where(
            RefreshToken.id.in_(list(token_ids))
        )
    )
    return {row.id: (row.revoked_at, row.revoke_reason) for row in rows}


async def _token_id_by_raw(db: AsyncSession, raw: str) -> uuid.UUID | None:
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    return await db.scalar(
        select(RefreshToken.id).where(RefreshToken.token_hash == token_hash)
    )


@pytest.mark.tc("AUTH-21")
async def test_lock_active_user_returns_locked_admin_out(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    demo = persona_id(3)
    res = await client.post(
        _action_url(demo, "lock"), headers=await auth_headers("admin")
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == ADMIN_OUT_KEYS
    assert body["id"] == demo
    assert body["status"] == "locked"
    assert (await _user_state(db, demo))[0] == UserStatus.LOCKED


@pytest.mark.tc("AUTH-21")
async def test_lock_active_user_revokes_every_refresh_token_as_admin_revoked(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    demo = persona_id(3)
    # Đăng nhập thật để có thêm một refresh token chưa thu hồi (thiết bị web);
    # fixture auth_headers chỉ tạo access token, không ghi refresh token.
    login = await _login(client, "demo@smartworkout.local")
    assert login.status_code == 200, login.text
    active_before = await _unrevoked_token_ids(db, demo)
    assert len(active_before) >= 2
    assert await _token_id_by_raw(db, DEMO_REFRESH) in active_before

    res = await client.post(
        _action_url(demo, "lock"), headers=await auth_headers("admin")
    )
    assert res.status_code == 200, res.text

    after = await _revocations(db, active_before)
    assert set(after) == active_before
    assert all(
        revoked_at is not None and reason == TokenRevokeReason.ADMIN_REVOKED
        for revoked_at, reason in after.values()
    )
    assert await _unrevoked_token_ids(db, demo) == set()
    refresh = await client.post(REFRESH, json={"refresh_token": DEMO_REFRESH})
    _assert_error(refresh, 401, "token_invalid")


@pytest.mark.tc("AUTH-21")
async def test_lock_active_user_rejects_old_access_token_and_login(
    client: AsyncClient, auth_headers
):
    demo_headers = await auth_headers("demo")
    me_before = await client.get(ME, headers=demo_headers)
    assert me_before.status_code == 200, me_before.text

    res = await client.post(
        _action_url(persona_id(3), "lock"), headers=await auth_headers("admin")
    )
    assert res.status_code == 200, res.text

    _assert_error(await client.get(ME, headers=demo_headers), 401, "token_invalid")
    login = await _login(client, "demo@smartworkout.local")
    _assert_error(login, 423, "account_locked")


@pytest.mark.tc("AUTH-22")
async def test_unlock_locked_user_returns_active_and_allows_login(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    locked = persona_id(12)
    assert (await _user_state(db, locked))[0] == UserStatus.LOCKED

    res = await client.post(
        _action_url(locked, "unlock"), headers=await auth_headers("admin")
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == ADMIN_OUT_KEYS
    assert body["id"] == locked
    assert body["status"] == "active"
    assert body["locked_until"] is None
    assert await _user_state(db, locked) == (UserStatus.ACTIVE, None)

    login = await _login(client, "locked@smartworkout.local")
    assert login.status_code == 200, login.text


@pytest.mark.tc("AUTH-23")
@pytest.mark.parametrize("action", ["lock", "unlock"])
@pytest.mark.parametrize(
    "user_id", [str(uuid.uuid4()), persona_id(14)], ids=["random_uuid", "soft_deleted"]
)
async def test_lock_or_unlock_unknown_or_deleted_user_returns_not_found(
    client: AsyncClient, auth_headers, action: str, user_id: str
):
    res = await client.post(
        _action_url(user_id, action), headers=await auth_headers("admin")
    )
    _assert_error(res, 404, "user_not_found")


@pytest.mark.tc("AUTH-23")
async def test_lock_self_returns_conflict_and_keeps_admin_active(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    admin = persona_id(1)
    headers = await auth_headers("admin")
    state_before = await _user_state(db, admin)
    tokens_before = await _unrevoked_token_ids(db, admin)
    assert state_before[0] == UserStatus.ACTIVE

    res = await client.post(_action_url(admin, "lock"), headers=headers)
    _assert_error(res, 409, "conflict")
    assert await _user_state(db, admin) == state_before
    assert await _unrevoked_token_ids(db, admin) == tokens_before


@pytest.mark.tc("AUTH-23")
async def test_unlock_disabled_user_returns_conflict_and_keeps_disabled(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    disabled = persona_id(13)
    state_before = await _user_state(db, disabled)
    assert state_before[0] == UserStatus.DISABLED

    res = await client.post(
        _action_url(disabled, "unlock"), headers=await auth_headers("admin")
    )
    _assert_error(res, 409, "conflict")
    assert await _user_state(db, disabled) == state_before


@pytest.mark.parametrize(
    "case",
    [("lock", 13), ("lock", 11), ("unlock", 11)],
    ids=["lock_disabled", "lock_pending", "unlock_pending"],
)
async def test_lock_or_unlock_disabled_or_pending_user_returns_conflict_unchanged(
    client: AsyncClient, db: AsyncSession, auth_headers, case: tuple[str, int]
):
    action, nn = case
    user_id = persona_id(nn)
    state_before = await _user_state(db, user_id)
    tokens_before = await _unrevoked_token_ids(db, user_id)
    res = await client.post(
        _action_url(user_id, action), headers=await auth_headers("admin")
    )
    _assert_error(res, 409, "conflict")
    assert await _user_state(db, user_id) == state_before
    assert await _unrevoked_token_ids(db, user_id) == tokens_before


async def test_lock_already_locked_user_returns_locked(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    locked = persona_id(12)
    res = await client.post(
        _action_url(locked, "lock"), headers=await auth_headers("admin")
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "locked"
    assert (await _user_state(db, locked))[0] == UserStatus.LOCKED
    assert await _unrevoked_token_ids(db, locked) == set()


async def test_unlock_active_user_returns_active_unchanged(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    demo = persona_id(3)
    res = await client.post(
        _action_url(demo, "unlock"), headers=await auth_headers("admin")
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "active"
    assert res.json()["locked_until"] is None
    assert await _user_state(db, demo) == (UserStatus.ACTIVE, None)


# --- AUTH-24, AUTH-25: /users* thiếu token / thiếu permission ---
TARGET_ID = persona_id(3)
Endpoint = tuple[str, str, dict | None]
USERS_ENDPOINTS: list[Endpoint] = [
    ("GET", USERS, None),
    ("GET", f"{USERS}/{TARGET_ID}", None),
    ("PUT", _roles_url(TARGET_ID), EDITOR_AND_USER),
    ("POST", _action_url(TARGET_ID, "lock"), None),
    ("POST", _action_url(TARGET_ID, "unlock"), None),
]
USERS_ENDPOINT_IDS = ["list_users", "get_user", "replace_roles", "lock", "unlock"]
# demo (role user) và editor (role content_editor) đều không có user:read, role:assign, user:lock.
NO_PERMISSION_PERSONAS = ("demo", "editor")
NO_PERMISSION_CASES = list(itertools.product(NO_PERMISSION_PERSONAS, USERS_ENDPOINTS))
NO_PERMISSION_IDS = [
    f"{persona}-{endpoint_id}"
    for persona, endpoint_id in itertools.product(NO_PERMISSION_PERSONAS, USERS_ENDPOINT_IDS)
]


class UserSnapshot(NamedTuple):
    """Dữ liệu của một user mà các endpoint /auth, /users có thể đổi."""

    state: UserState
    password: tuple
    profile: tuple
    unrevoked_token_ids: set[uuid.UUID]
    active_roles: set[str]


async def _user_snapshot(db: AsyncSession, user_id: str) -> UserSnapshot:
    """Đọc thẳng cột từ DB (không qua identity map) để so sánh trước/sau một request."""
    uid = uuid.UUID(user_id)
    password = (
        await db.execute(select(User.password_hash, User.password_changed_at).where(User.id == uid))
    ).one()
    profile = (
        await db.execute(
            select(
                UserProfile.display_name,
                UserProfile.full_name,
                UserProfile.locale,
                UserProfile.timezone,
                UserProfile.unit_system,
            ).where(UserProfile.user_id == uid)
        )
    ).one()
    return UserSnapshot(
        state=await _user_state(db, user_id),
        password=tuple(password),
        profile=tuple(profile),
        unrevoked_token_ids=await _unrevoked_token_ids(db, user_id),
        active_roles=await _active_role_codes(db, user_id),
    )


@pytest.mark.tc("AUTH-24")
@pytest.mark.parametrize("endpoint", USERS_ENDPOINTS, ids=USERS_ENDPOINT_IDS)
async def test_users_endpoints_without_token_return_token_invalid(
    client: AsyncClient, db: AsyncSession, endpoint: Endpoint
):
    method, url, body = endpoint
    before = await _user_snapshot(db, TARGET_ID)

    res = await client.request(method, url, json=body)

    _assert_error(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"
    assert await _user_snapshot(db, TARGET_ID) == before


@pytest.mark.tc("AUTH-25")
@pytest.mark.parametrize("case", NO_PERMISSION_CASES, ids=NO_PERMISSION_IDS)
@pytest.mark.usefixtures("perm_cache")
async def test_users_endpoints_without_permission_return_permission_denied(
    client: AsyncClient, db: AsyncSession, auth_headers, case: tuple[str, Endpoint]
):
    persona, (method, url, body) = case
    headers = await auth_headers(persona)
    # Chụp sau khi đăng nhập: login của demo thêm một refresh token mới cho …03.
    before = await _user_snapshot(db, TARGET_ID)
    assert before.state[0] == UserStatus.ACTIVE
    assert before.active_roles == {"user"}

    res = await client.request(method, url, json=body, headers=headers)

    _assert_error(res, 403, "permission_denied")
    assert await _user_snapshot(db, TARGET_ID) == before
