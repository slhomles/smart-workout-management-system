"""Integration test /users (quản trị người dùng) trên PostgreSQL thật (persona seed, docs/database/test-dataset.md)."""

import uuid
from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import Role, User, UserRole
from app.models.enums import UserStatus
from tests.conftest import persona_id

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
