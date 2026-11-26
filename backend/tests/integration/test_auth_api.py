"""Integration test /auth trên PostgreSQL thật (persona seed, xem docs/database/test-dataset.md)."""

import hashlib
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import LoginAttempt, RefreshToken, User, UserDevice
from tests.conftest import SEED_PASSWORD, persona_id

LOGIN = "/api/v1/auth/login"


def _login_body(persona: str, password: str = SEED_PASSWORD) -> dict:
    return {"email": f"{persona}@smartworkout.local", "password": password, "device": {"platform": "android"}}


def _assert_error(res, status: int, code: str) -> dict:
    assert res.status_code == status, res.text
    body = res.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["details"], list)
    assert body["error"]["request_id"] == res.headers["X-Request-ID"]
    return body["error"]


async def test_login_demo_success_returns_tokens(client: AsyncClient):
    res = await client.post(LOGIN, json=_login_body("demo"))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 1800
    assert body["user"]["id"] == persona_id(3)
    assert body["user"]["roles"] == ["user"]
    assert "success" not in body and "data" not in body


async def test_login_email_is_case_insensitive(client: AsyncClient):
    res = await client.post(LOGIN, json={**_login_body("demo"), "email": "DEMO@SmartWorkout.Local"})
    assert res.status_code == 200, res.text


async def test_login_wrong_password_invalid_credentials(client: AsyncClient):
    _assert_error(await client.post(LOGIN, json=_login_body("demo", "Sai@1234")), 401, "invalid_credentials")


async def test_login_unknown_deleted_and_oauth_only_same_error(client: AsyncClient):
    for persona in ("khongtontai", "deleted", "oauth"):
        _assert_error(await client.post(LOGIN, json=_login_body(persona)), 401, "invalid_credentials")


async def test_login_five_failures_lock_account(client: AsyncClient):
    for _ in range(5):
        _assert_error(await client.post(LOGIN, json=_login_body("newbie", "Sai@1234")), 401, "invalid_credentials")
    error = _assert_error(await client.post(LOGIN, json=_login_body("newbie")), 423, "account_locked")
    assert error["details"][0]["code"] == "retry_after_seconds"


async def test_login_status_errors(client: AsyncClient):
    _assert_error(await client.post(LOGIN, json=_login_body("locked")), 423, "account_locked")
    _assert_error(await client.post(LOGIN, json=_login_body("disabled")), 403, "account_disabled")
    _assert_error(await client.post(LOGIN, json=_login_body("pending")), 403, "email_not_verified")


async def test_login_validation_error_format(client: AsyncClient):
    error = _assert_error(await client.post(LOGIN, json={"email": "demo@smartworkout.local"}), 422, "validation_error")
    fields = {d["field"] for d in error["details"]}
    assert {"password", "device"} <= fields


async def test_refresh_rotates_token(client: AsyncClient):
    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": "seed-refresh-demo-2"})
    assert res.status_code == 200, res.text
    new_token = res.json()["refresh_token"]
    # token cũ đã xoay vòng → gửi lại bị phát hiện
    _assert_error(await client.post("/api/v1/auth/refresh", json={"refresh_token": "seed-refresh-demo-2"}), 401, "token_reused")
    # cả family bị thu hồi → token mới cũng hết hiệu lực
    _assert_error(await client.post("/api/v1/auth/refresh", json={"refresh_token": new_token}), 401, "token_invalid")


async def test_refresh_error_cases(client: AsyncClient):
    cases = {
        "seed-refresh-demo-1": "token_reused",
        "seed-refresh-dung-exp": "token_expired",
        "seed-refresh-locked-2": "token_invalid",
        "seed-refresh-disabled-1": "token_invalid",
        "khong-ton-tai": "token_invalid",
    }
    for token, code in cases.items():
        _assert_error(await client.post("/api/v1/auth/refresh", json={"refresh_token": token}), 401, code)


async def test_me_requires_token(client: AsyncClient):
    _assert_error(await client.get("/api/v1/auth/me"), 401, "token_invalid")
    _assert_error(
        await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer abc.def.ghi"}), 401, "token_invalid"
    )


async def test_me_returns_profile_and_permissions(client: AsyncClient, auth_headers):
    res = await client.get("/api/v1/auth/me", headers=await auth_headers("demo"))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["display_name"] == "An"
    assert "body_metric:manage_own" in body["permissions"]
    assert "workout:manage_own" in body["permissions"]


async def test_me_trainer_expired_role_ignored(client: AsyncClient, auth_headers):
    body = (await client.get("/api/v1/auth/me", headers=await auth_headers("trainer"))).json()
    assert body["roles"] == ["user"]
    assert "exercise:create" not in body["permissions"]


async def test_logout_is_idempotent(client: AsyncClient):
    login = (await client.post(LOGIN, json=_login_body("demo"))).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    first = await client.post("/api/v1/auth/logout", json={"refresh_token": login["refresh_token"]}, headers=headers)
    assert first.status_code == 200 and first.json() == {"is_revoked": True}
    second = await client.post("/api/v1/auth/logout", json={"refresh_token": login["refresh_token"]}, headers=headers)
    assert second.status_code == 200 and second.json() == {"is_revoked": False}
    _assert_error(
        await client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}), 401, "token_invalid"
    )


async def test_unknown_route_uses_error_format(client: AsyncClient):
    _assert_error(await client.get("/api/v1/khong-co"), 404, "http_404")


# ---------------------------------------------------------------------------
# AUTH-04, AUTH-05, AUTH-06: POST /auth/login (spec docs/features/auth-users.md §5)
# ---------------------------------------------------------------------------

DEMO_ID = persona_id(3)
POWER_ID = persona_id(4)
NEWBIE_ID = persona_id(8)
LOCKED_ID = persona_id(12)


async def _device_id(db: AsyncSession, user_nn: int, device_name: str) -> uuid.UUID:
    return (
        await db.execute(
            select(UserDevice.id).where(
                UserDevice.user_id == uuid.UUID(persona_id(user_nn)), UserDevice.device_name == device_name
            )
        )
    ).scalar_one()


async def _max_attempt_id(db: AsyncSession) -> int:
    return (await db.scalar(select(func.coalesce(func.max(LoginAttempt.id), 0)))) or 0


async def _attempts_after(db: AsyncSession, email: str, after_id: int) -> list:
    """Dòng `auth.login_attempts` mới (id > after_id) theo `email_attempted` (citext)."""
    rows = await db.execute(
        select(LoginAttempt.user_id, LoginAttempt.succeeded, LoginAttempt.failure_reason)
        .where(LoginAttempt.id > after_id, LoginAttempt.email_attempted == email)
        .order_by(LoginAttempt.id)
    )
    return list(rows.all())


async def _count_demo_successes(db: AsyncSession) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(LoginAttempt)
        .where(LoginAttempt.user_id == uuid.UUID(DEMO_ID), LoginAttempt.succeeded.is_(True))
    ) or 0


@pytest.mark.tc("AUTH-04")
@pytest.mark.parametrize("case", ["a_no_device_id", "b_own_pixel_device", "c_other_user_iphone_device"])
async def test_login_demo_valid_password_returns_tokens_and_persists_session(
    client: AsyncClient, db: AsyncSession, case: str
):
    pixel_id = await _device_id(db, 3, "Pixel 8 của An")
    iphone_id = await _device_id(db, 4, "iPhone 15 Pro")
    power_device_ids = set(
        (await db.execute(select(UserDevice.id).where(UserDevice.user_id == uuid.UUID(POWER_ID)))).scalars()
    )
    assert iphone_id in power_device_ids

    payload = _login_body("demo")
    if case == "b_own_pixel_device":
        payload["device"]["device_id"] = str(pixel_id)
    elif case == "c_other_user_iphone_device":
        payload["device"]["device_id"] = str(iphone_id)

    successes_before = await _count_demo_successes(db)
    res = await client.post(LOGIN, json=payload)

    assert res.status_code == 200, res.text
    body = res.json()
    assert "success" not in body and "data" not in body
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 1800
    assert body["user"]["id"] == DEMO_ID
    assert body["user"]["roles"] == ["user"]
    raw_refresh = body["refresh_token"]
    device_id = uuid.UUID(body["device_id"])

    # refresh token: DB chỉ lưu sha256, không cột nào chứa token gốc (doc 04 §3.2)
    token_hash = hashlib.sha256(raw_refresh.encode("utf-8")).hexdigest()
    token_rows = (
        await db.execute(text("SELECT * FROM auth.refresh_tokens WHERE token_hash = :h"), {"h": token_hash})
    ).mappings().all()
    assert len(token_rows) == 1
    token_row = token_rows[0]
    assert token_row["device_id"] == device_id
    assert token_row["revoked_at"] is None
    for column, value in token_row.items():
        assert value is None or raw_refresh not in str(value), f"cột {column} chứa token gốc"
    assert await db.scalar(select(func.count()).select_from(RefreshToken).where(RefreshToken.token_hash == raw_refresh)) == 0

    # login_attempts: thêm đúng một dòng succeeded=true của …03
    assert await _count_demo_successes(db) == successes_before + 1

    # thiết bị
    device_owner = (
        await db.execute(select(UserDevice.user_id).where(UserDevice.id == device_id))
    ).scalar_one()
    assert device_owner == uuid.UUID(DEMO_ID)
    if case == "b_own_pixel_device":
        assert device_id == pixel_id
    else:
        assert device_id != pixel_id
        assert device_id != iphone_id
        assert device_id not in power_device_ids
    # thiết bị của power@ không bị chuyển chủ
    iphone_owner = (await db.execute(select(UserDevice.user_id).where(UserDevice.id == iphone_id))).scalar_one()
    assert iphone_owner == uuid.UUID(POWER_ID)


@pytest.mark.tc("AUTH-05")
async def test_login_invalid_or_blocked_account_returns_error_and_logs_one_attempt(
    client: AsyncClient, db: AsyncSession
):
    # Seed định nghĩa locked@ có `locked_until = now() + 30 phút` tính tại lúc init (test-dataset §2).
    # Dựng lại đúng tiền điều kiện đó trong transaction của test (bị rollback) để không phụ thuộc thời điểm seed.
    await db.execute(
        text("UPDATE auth.users SET locked_until = now() + interval '30 minutes' WHERE id = :id"),
        {"id": LOCKED_ID},
    )

    # (body, status, code, failure_reason, user_id kỳ vọng của dòng login_attempts; None = không kiểm user_id)
    cases = [
        (_login_body("demo", "Sai@1234"), 401, "invalid_credentials", "invalid_credentials", DEMO_ID),
        (_login_body("khongtontai"), 401, "invalid_credentials", "invalid_credentials", None),
        (_login_body("deleted"), 401, "invalid_credentials", "invalid_credentials", None),
        (_login_body("oauth"), 401, "invalid_credentials", "invalid_credentials", persona_id(15)),
        (_login_body("disabled"), 403, "account_disabled", "account_disabled", persona_id(13)),
        (_login_body("pending"), 403, "email_not_verified", "email_not_verified", persona_id(11)),
        (_login_body("locked"), 423, "account_locked", "account_locked", LOCKED_ID),
    ]

    invalid_messages: set[str] = set()
    for body, status, code, reason, expected_user in cases:
        before = await _max_attempt_id(db)
        error = _assert_error(await client.post(LOGIN, json=body), status, code)
        assert isinstance(error["message"], str) and error["message"]
        if code == "invalid_credentials":
            invalid_messages.add(error["message"])
        if code == "account_locked":
            assert error["details"][0]["code"] == "retry_after_seconds"
            assert int(error["details"][0]["message"]) > 0

        attempts = await _attempts_after(db, body["email"], before)
        assert len(attempts) == 1, (body["email"], attempts)
        user_id, succeeded, failure_reason = attempts[0]
        assert succeeded is False
        assert failure_reason == reason
        if expected_user is not None:
            assert user_id == uuid.UUID(expected_user)

    # 4 ca đầu cùng một message để không lộ email nào tồn tại
    assert len(invalid_messages) == 1


@pytest.mark.tc("AUTH-06")
async def test_login_five_wrong_passwords_then_correct_password_returns_locked(
    client: AsyncClient, db: AsyncSession
):
    for _ in range(5):
        _assert_error(await client.post(LOGIN, json=_login_body("newbie", "Sai@1234")), 401, "invalid_credentials")

    error = _assert_error(await client.post(LOGIN, json=_login_body("newbie")), 423, "account_locked")
    assert error["details"][0]["code"] == "retry_after_seconds"
    assert int(error["details"][0]["message"]) > 0

    locked_until = (
        await db.execute(select(User.locked_until).where(User.id == uuid.UUID(NEWBIE_ID)))
    ).scalar_one()
    db_now = await db.scalar(select(func.now()))
    assert locked_until is not None
    assert locked_until > db_now
