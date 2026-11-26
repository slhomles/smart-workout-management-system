"""Integration test /auth trên PostgreSQL thật (persona seed, xem docs/database/test-dataset.md)."""

import hashlib
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import cast, func, select, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.crud import auth as auth_crud
from app.models.auth import LoginAttempt, RefreshToken, Role, User, UserDevice, UserProfile, UserRole
from app.models.enums import TokenRevokeReason
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


# ---------------------------------------------------------------------------
# AUTH-07, AUTH-08, AUTH-09, AUTH-11: refresh / logout / me (spec docs/features/auth-users.md §5)
# ---------------------------------------------------------------------------

REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"


def _sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _token_row(db: AsyncSession, raw: str):
    """Đọc cột của `auth.refresh_tokens` theo token gốc (truy vấn cột → không dính cache identity map)."""
    return (
        await db.execute(
            select(
                RefreshToken.id,
                RefreshToken.device_id,
                RefreshToken.family_id,
                RefreshToken.parent_token_id,
                RefreshToken.revoked_at,
                RefreshToken.revoke_reason,
            ).where(RefreshToken.token_hash == _sha256(raw))
        )
    ).one()


@pytest.mark.tc("AUTH-07")
async def test_refresh_valid_then_reused_token_rotates_and_revokes_family(client: AsyncClient, db: AsyncSession):
    old_raw = "seed-refresh-demo-2"
    pixel_id = await _device_id(db, 3, "Pixel 8 của An")
    old_before = await _token_row(db, old_raw)
    assert old_before.revoked_at is None

    # Lần 1: xoay vòng thành công
    res = await client.post(REFRESH, json={"refresh_token": old_raw})
    assert res.status_code == 200, res.text
    body = res.json()
    assert "user" not in body
    assert isinstance(body["access_token"], str) and body["access_token"]
    new_raw = body["refresh_token"]
    assert isinstance(new_raw, str) and new_raw and new_raw != old_raw
    assert body["expires_in"] == 1800
    assert uuid.UUID(body["device_id"]) == pixel_id

    old_row = await _token_row(db, old_raw)
    new_row = await _token_row(db, new_raw)
    assert old_row.revoked_at is not None
    assert old_row.revoke_reason == TokenRevokeReason.ROTATED
    assert new_row.revoked_at is None
    assert new_row.family_id == old_row.family_id
    assert new_row.parent_token_id == old_row.id
    assert new_row.device_id == pixel_id

    # Lần 2: gửi lại token đã xoay vòng → phát hiện tái sử dụng
    _assert_error(await client.post(REFRESH, json={"refresh_token": old_raw}), 401, "token_reused")

    # Lần 3: token mới cũng đã bị thu hồi theo family
    _assert_error(await client.post(REFRESH, json={"refresh_token": new_raw}), 401, "token_invalid")

    family_rows = (
        await db.execute(
            select(RefreshToken.id, RefreshToken.revoked_at, RefreshToken.revoke_reason).where(
                RefreshToken.family_id == old_row.family_id
            )
        )
    ).all()
    assert {row.id for row in family_rows} >= {old_row.id, new_row.id}
    assert all(row.revoked_at is not None for row in family_rows)
    reasons = {row.id: row.revoke_reason for row in family_rows}
    assert reasons[old_row.id] == TokenRevokeReason.ROTATED
    assert reasons[new_row.id] == TokenRevokeReason.REUSE_DETECTED


@pytest.mark.tc("AUTH-08")
@pytest.mark.parametrize(
    ("payload", "status", "code"),
    [
        ({"refresh_token": "seed-refresh-demo-1"}, 401, "token_reused"),
        ({"refresh_token": "seed-refresh-dung-exp"}, 401, "token_expired"),
        ({"refresh_token": "seed-refresh-locked-2"}, 401, "token_invalid"),
        ({"refresh_token": "seed-refresh-disabled-1"}, 401, "token_invalid"),
        ({"refresh_token": "khong-ton-tai"}, 401, "token_invalid"),
        ({}, 422, "validation_error"),
    ],
    ids=["demo_1_rotated", "dung_exp_expired", "locked_2_reuse_detected", "disabled_1_admin_revoked", "unknown", "empty"],
)
async def test_refresh_invalid_token_returns_matching_error(client: AsyncClient, payload: dict, status: int, code: str):
    error = _assert_error(await client.post(REFRESH, json=payload), status, code)
    assert isinstance(error["message"], str) and error["message"]
    if code == "validation_error":
        assert any(d["field"] == "refresh_token" for d in error["details"])


@pytest.mark.tc("AUTH-09")
async def test_logout_own_token_twice_and_other_user_token_is_idempotent(client: AsyncClient, db: AsyncSession):
    login = await client.post(LOGIN, json=_login_body("demo"))
    assert login.status_code == 200, login.text
    login_body = login.json()
    headers = {"Authorization": f"Bearer {login_body['access_token']}"}
    own_raw = login_body["refresh_token"]

    first = await client.post(LOGOUT, json={"refresh_token": own_raw}, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json() == {"is_revoked": True}

    second = await client.post(LOGOUT, json={"refresh_token": own_raw}, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json() == {"is_revoked": False}

    own_row = await _token_row(db, own_raw)
    assert own_row.revoked_at is not None
    assert own_row.revoke_reason == TokenRevokeReason.LOGOUT
    _assert_error(await client.post(REFRESH, json={"refresh_token": own_raw}), 401, "token_invalid")

    # Token của power@: demo không thu hồi được
    power_raw = "seed-refresh-power-ios"
    other = await client.post(LOGOUT, json={"refresh_token": power_raw}, headers=headers)
    assert other.status_code == 200, other.text
    assert other.json() == {"is_revoked": False}
    power_row = await _token_row(db, power_raw)
    assert power_row.revoked_at is None

    power_refresh = await client.post(REFRESH, json={"refresh_token": power_raw})
    assert power_refresh.status_code == 200, power_refresh.text
    assert isinstance(power_refresh.json()["access_token"], str) and power_refresh.json()["access_token"]


@pytest.mark.tc("AUTH-11")
async def test_me_demo_trainer_editor_returns_profile_roles_and_permissions(client: AsyncClient, auth_headers):
    demo = await client.get(ME, headers=await auth_headers("demo"))
    assert demo.status_code == 200, demo.text
    body = demo.json()
    assert "password_hash" not in body
    assert body["id"] == DEMO_ID
    assert body["display_name"] == "An"
    assert body["full_name"] == "Nguyễn Văn An"
    assert body["locale"] == "vi-VN"
    assert body["timezone"] == "Asia/Ho_Chi_Minh"
    assert body["unit_system"] == "metric"
    assert body["status"] == "active"
    assert body["roles"] == ["user"]
    assert "workout:manage_own" in body["permissions"]
    assert "user:read" not in body["permissions"]

    trainer = await client.get(ME, headers=await auth_headers("trainer"))
    assert trainer.status_code == 200, trainer.text
    trainer_body = trainer.json()
    assert trainer_body["roles"] == ["user"]
    assert "exercise:create" not in trainer_body["permissions"]

    editor = await client.get(ME, headers=await auth_headers("editor"))
    assert editor.status_code == 200, editor.text
    editor_body = editor.json()
    assert editor_body["roles"] == ["content_editor"]
    assert "exercise:create" in editor_body["permissions"]
    assert "workout:manage_own" not in editor_body["permissions"]


# ---------------------------------------------------------------------------
# AUTH-01, AUTH-02, AUTH-03: POST /auth/register (spec docs/features/auth-users.md §5)
# ---------------------------------------------------------------------------

REGISTER = "/api/v1/auth/register"
DELETED_ID = persona_id(14)
REGISTER_KEYS = {"id", "email", "display_name", "full_name", "roles", "status"}


def _register_body(**overrides) -> dict:
    body = {
        "email": "moi.user@example.com",
        "password": "Moi@12345",
        "display_name": "Mới",
        "full_name": "Người Mới",
    }
    body.update(overrides)
    return body


async def _count_users(db: AsyncSession, email: str | None = None) -> int:
    """Đếm `auth.users` (kể cả đã xoá mềm); có `email` thì lọc theo email (citext, không phân biệt hoa thường)."""
    query = select(func.count()).select_from(User)
    if email is not None:
        query = query.where(User.email == cast(email, CITEXT))
    return await db.scalar(query) or 0


@pytest.mark.tc("AUTH-01")
@pytest.mark.parametrize(
    "email",
    ["moi.user@example.com", "deleted@smartworkout.local"],
    ids=["a_new_email", "b_soft_deleted_email"],
)
async def test_register_valid_body_returns_201_and_creates_user_profile_role(
    client: AsyncClient, db: AsyncSession, email: str
):
    payload = _register_body(email=email)

    res = await client.post(REGISTER, json=payload)

    assert res.status_code == 201, res.text
    body = res.json()
    assert set(body) == REGISTER_KEYS
    user_id = uuid.UUID(body["id"])
    assert res.headers["Location"] == f"/api/v1/users/{body['id']}"
    assert body["email"] == email
    assert body["display_name"] == "Mới"
    assert body["full_name"] == "Người Mới"
    assert body["roles"] == ["user"]
    assert body["status"] == "active"
    assert "password" not in res.text and "password_hash" not in res.text

    # auth.users: đúng 1 dòng, mật khẩu đã băm bcrypt, email đã xác thực (REQUIRE_EMAIL_VERIFICATION=false)
    users = (
        await db.execute(
            select(User.email, User.password_hash, User.status, User.email_verified_at, User.deleted_at).where(
                User.id == user_id
            )
        )
    ).all()
    assert len(users) == 1
    user = users[0]
    assert user.email == email
    assert user.password_hash is not None
    assert user.password_hash != payload["password"]
    assert verify_password(payload["password"], user.password_hash)
    assert user.status == "active"
    assert user.email_verified_at is not None
    assert user.deleted_at is None

    # auth.user_profiles: đúng 1 dòng; locale/timezone/unit_system lấy DEFAULT của DB
    profiles = (
        await db.execute(
            select(
                UserProfile.display_name,
                UserProfile.full_name,
                UserProfile.locale,
                UserProfile.timezone,
                UserProfile.unit_system,
            ).where(UserProfile.user_id == user_id)
        )
    ).all()
    assert [tuple(p) for p in profiles] == [("Mới", "Người Mới", "vi-VN", "Asia/Ho_Chi_Minh", "metric")]

    # auth.user_roles: đúng 1 dòng role `user`, không người cấp, vô thời hạn
    roles = (
        await db.execute(
            select(Role.code, UserRole.granted_by, UserRole.expires_at)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id == user_id)
        )
    ).all()
    assert [tuple(r) for r in roles] == [("user", None, None)]

    # Đăng nhập được bằng thông tin vừa đăng ký
    login = await client.post(
        LOGIN, json={"email": email, "password": payload["password"], "device": {"platform": "android"}}
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["id"] == body["id"]
    assert login.json()["user"]["roles"] == ["user"]

    if email.startswith("deleted@"):
        # Tài khoản mới, không "hồi sinh" …14; …14 vẫn ở trạng thái xoá mềm
        assert body["id"] != DELETED_ID
        old_deleted_at = (
            await db.execute(select(User.deleted_at).where(User.id == uuid.UUID(DELETED_ID)))
        ).scalar_one()
        assert old_deleted_at is not None
        assert await _count_users(db, email) == 2


@pytest.mark.tc("AUTH-01")
async def test_register_padded_display_name_without_full_name_stores_stripped_and_null(
    client: AsyncClient, db: AsyncSession
):
    payload = _register_body(display_name="  Mới  ")
    del payload["full_name"]

    res = await client.post(REGISTER, json=payload)

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["display_name"] == "Mới"
    assert body["full_name"] is None
    profile = (
        await db.execute(
            select(UserProfile.display_name, UserProfile.full_name).where(
                UserProfile.user_id == uuid.UUID(body["id"])
            )
        )
    ).one()
    assert tuple(profile) == ("Mới", None)


@pytest.mark.tc("AUTH-02")
@pytest.mark.parametrize(
    "email", ["demo@smartworkout.local", "DEMO@SmartWorkout.Local"], ids=["same_case", "different_case"]
)
async def test_register_email_of_alive_account_returns_409_email_already_exists(
    client: AsyncClient, db: AsyncSession, email: str
):
    by_email_before = await _count_users(db, email)
    total_before = await _count_users(db)
    assert by_email_before >= 1

    res = await client.post(REGISTER, json=_register_body(email=email, display_name="Trùng"))

    _assert_error(res, 409, "email_already_exists")
    assert await _count_users(db, email) == by_email_before
    assert await _count_users(db) == total_before


@pytest.mark.tc("AUTH-02")
async def test_register_concurrent_duplicate_email_returns_409_email_already_exists(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """Mô phỏng hai request đăng ký đồng thời: bước kiểm tra trước không thấy email, INSERT vướng uq_users_email_alive."""
    real_get_user_by_email = auth_crud.get_user_by_email
    calls = {"n": 0}

    async def first_call_misses(session: AsyncSession, email: str) -> User | None:
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return await real_get_user_by_email(session, email)

    monkeypatch.setattr(auth_crud, "get_user_by_email", first_call_misses)
    email = "demo@smartworkout.local"
    by_email_before = await _count_users(db, email)
    total_before = await _count_users(db)

    res = await client.post(REGISTER, json=_register_body(email=email))

    _assert_error(res, 409, "email_already_exists")
    assert calls["n"] == 2
    assert await _count_users(db, email) == by_email_before
    assert await _count_users(db) == total_before


_ACCENTED_PASSWORD = "Aa1" + "é" * 35


@pytest.mark.tc("AUTH-03")
@pytest.mark.parametrize(
    ("overrides", "drop", "expected_field"),
    [
        ({"password": "abcdefgh"}, None, "password"),
        ({"password": "12345678"}, None, "password"),
        ({"password": "Ab1"}, None, "password"),
        ({"password": _ACCENTED_PASSWORD}, None, "password"),
        ({"email": "khong-phai-email"}, None, "email"),
        ({}, "display_name", "display_name"),
        ({"display_name": "   "}, None, "display_name"),
        ({"status": "active"}, None, "status"),
    ],
    ids=[
        "password_no_digit",
        "password_no_letter",
        "password_too_short",
        "password_73_utf8_bytes",
        "email_bad_format",
        "display_name_missing",
        "display_name_blank",
        "extra_field_status",
    ],
)
async def test_register_invalid_body_returns_422_validation_error_without_creating_user(
    client: AsyncClient, db: AsyncSession, overrides: dict, drop: str | None, expected_field: str
):
    if overrides.get("password") == _ACCENTED_PASSWORD:
        # 38 ký tự (trong khoảng 8–72) nhưng 73 byte UTF-8 → validator phải đếm byte, không đếm ký tự
        assert len(_ACCENTED_PASSWORD) == 38
        assert len(_ACCENTED_PASSWORD.encode("utf-8")) == 73
    payload = _register_body(**overrides)
    if drop is not None:
        del payload[drop]
    total_before = await _count_users(db)
    by_email_before = await _count_users(db, payload["email"])

    res = await client.post(REGISTER, json=payload)

    error = _assert_error(res, 422, "validation_error")
    assert expected_field in [d["field"] for d in error["details"]], error["details"]
    if "password" in overrides:
        # Không phản hồi lại mật khẩu trong thông báo lỗi
        assert all(overrides["password"] not in d["message"] for d in error["details"])
    assert await _count_users(db) == total_before
    assert await _count_users(db, payload["email"]) == by_email_before
