"""Integration test /auth trên PostgreSQL thật (persona seed, xem docs/database/test-dataset.md)."""

import hashlib
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import cast, delete, func, select, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, verify_password
from app.crud import auth as auth_crud
from app.models.auth import LoginAttempt, RefreshToken, Role, User, UserDevice, UserProfile, UserRole
from app.models.enums import TokenRevokeReason
from app.schemas.auth import MeResponse
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


# ---------------------------------------------------------------------------
# AUTH-10, AUTH-14, AUTH-15: logout-all / change-password (spec docs/features/auth-users.md §5)
# ---------------------------------------------------------------------------

LOGOUT_ALL = "/api/v1/auth/logout-all"
CHANGE_PASSWORD = "/api/v1/auth/change-password"
OAUTH_ID = persona_id(15)
DEMO_REFRESH = "seed-refresh-demo-2"
POWER_REFRESH = "seed-refresh-power-web"
NEW_PASSWORD = "Moi@12345"


async def _user_tokens(db: AsyncSession, user_id: str, *, revoked: bool) -> dict[uuid.UUID, tuple]:
    """
    Refresh token thuộc mọi thiết bị của user, lọc theo đã/chưa thu hồi:
    id → (token_hash, revoked_at, revoke_reason). Truy vấn cột nên không dính identity map.
    """
    condition = RefreshToken.revoked_at.is_not(None) if revoked else RefreshToken.revoked_at.is_(None)
    rows = await db.execute(
        select(RefreshToken.id, RefreshToken.token_hash, RefreshToken.revoked_at, RefreshToken.revoke_reason)
        .join(UserDevice, UserDevice.id == RefreshToken.device_id)
        .where(UserDevice.user_id == uuid.UUID(user_id), condition)
    )
    return {row.id: (row.token_hash, row.revoked_at, row.revoke_reason) for row in rows}


async def _tokens_by_id(db: AsyncSession, ids) -> dict[uuid.UUID, tuple]:
    """id → (revoked_at, revoke_reason) của các refresh token theo id."""
    rows = await db.execute(
        select(RefreshToken.id, RefreshToken.revoked_at, RefreshToken.revoke_reason).where(RefreshToken.id.in_(ids))
    )
    return {row.id: (row.revoked_at, row.revoke_reason) for row in rows}


async def _password_state(db: AsyncSession, user_id: str) -> tuple:
    """(password_hash, password_changed_at) đọc thẳng từ `auth.users`."""
    row = (
        await db.execute(select(User.password_hash, User.password_changed_at).where(User.id == uuid.UUID(user_id)))
    ).one()
    return row.password_hash, row.password_changed_at


@pytest.mark.tc("AUTH-10")
async def test_logout_all_logged_in_user_revokes_tokens_of_every_device_and_returns_count(
    client: AsyncClient, db: AsyncSession
):
    login = await client.post(LOGIN, json=_login_body("demo"))
    assert login.status_code == 200, login.text
    login_body = login.json()
    raw_a = login_body["refresh_token"]
    headers = {"Authorization": f"Bearer {login_body['access_token']}"}

    active_before = await _user_tokens(db, DEMO_ID, revoked=False)
    revoked_before = await _user_tokens(db, DEMO_ID, revoked=True)
    active_hashes = {token_hash for token_hash, _, _ in active_before.values()}
    assert _sha256(raw_a) in active_hashes
    assert _sha256(DEMO_REFRESH) in active_hashes
    n = len(active_before)
    power_before = await _user_tokens(db, POWER_ID, revoked=False)
    assert _sha256(POWER_REFRESH) in {token_hash for token_hash, _, _ in power_before.values()}

    res = await client.post(LOGOUT_ALL, headers=headers)

    assert res.status_code == 200, res.text
    assert res.json() == {"revoked_count": n}

    # Đúng các token chưa thu hồi trước đó bị thu hồi với lý do `logout`
    after = await _tokens_by_id(db, list(active_before))
    assert set(after) == set(active_before)
    for revoked_at, reason in after.values():
        assert revoked_at is not None
        assert reason == TokenRevokeReason.LOGOUT
    assert await _user_tokens(db, DEMO_ID, revoked=False) == {}
    # Token đã thu hồi từ trước giữ nguyên thời điểm và lý do
    assert await _tokens_by_id(db, list(revoked_before)) == {
        token_id: (revoked_at, reason) for token_id, (_, revoked_at, reason) in revoked_before.items()
    }
    # Token của power@ không bị đụng tới
    assert await _user_tokens(db, POWER_ID, revoked=False) == power_before

    _assert_error(await client.post(REFRESH, json={"refresh_token": raw_a}), 401, "token_invalid")
    _assert_error(await client.post(REFRESH, json={"refresh_token": DEMO_REFRESH}), 401, "token_invalid")
    power = await client.post(REFRESH, json={"refresh_token": POWER_REFRESH})
    assert power.status_code == 200, power.text
    assert isinstance(power.json()["access_token"], str) and power.json()["access_token"]


@pytest.mark.tc("AUTH-14")
async def test_change_password_correct_current_password_updates_hash_and_revokes_all_tokens(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    headers = await auth_headers("demo")
    active_before = await _user_tokens(db, DEMO_ID, revoked=False)
    assert _sha256(DEMO_REFRESH) in {token_hash for token_hash, _, _ in active_before.values()}
    hash_before, changed_before = await _password_state(db, DEMO_ID)
    me = await client.get(ME, headers=headers)
    assert me.status_code == 200, me.text

    res = await client.patch(
        CHANGE_PASSWORD, json={"current_password": SEED_PASSWORD, "new_password": NEW_PASSWORD}, headers=headers
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == set(me.json()) == set(MeResponse.model_fields)
    assert body["id"] == DEMO_ID
    assert body["email"] == "demo@smartworkout.local"
    assert body["roles"] == ["user"]
    assert "password_hash" not in body
    assert NEW_PASSWORD not in res.text and SEED_PASSWORD not in res.text
    assert "access_token" not in body and "refresh_token" not in body

    # auth.users: hash mới khớp mật khẩu mới; password_changed_at = now() của DB
    hash_after, changed_after = await _password_state(db, DEMO_ID)
    assert hash_after != hash_before
    assert verify_password(NEW_PASSWORD, hash_after)
    assert not verify_password(SEED_PASSWORD, hash_after)
    assert changed_after is not None
    assert changed_after != changed_before
    assert changed_after == await db.scalar(select(func.now()))

    # Mọi refresh token chưa thu hồi trước đó (gồm seed-refresh-demo-2) bị thu hồi với lý do `password_changed`
    after = await _tokens_by_id(db, list(active_before))
    assert set(after) == set(active_before)
    for revoked_at, reason in after.values():
        assert revoked_at is not None
        assert reason == TokenRevokeReason.PASSWORD_CHANGED
    assert (await _token_row(db, DEMO_REFRESH)).revoke_reason == TokenRevokeReason.PASSWORD_CHANGED
    assert await _user_tokens(db, DEMO_ID, revoked=False) == {}
    _assert_error(await client.post(REFRESH, json={"refresh_token": DEMO_REFRESH}), 401, "token_invalid")

    _assert_error(await client.post(LOGIN, json=_login_body("demo")), 401, "invalid_credentials")
    login = await client.post(LOGIN, json=_login_body("demo", NEW_PASSWORD))
    assert login.status_code == 200, login.text
    assert login.json()["user"]["id"] == DEMO_ID


@pytest.mark.tc("AUTH-15")
@pytest.mark.parametrize(
    ("payload", "status", "code", "field"),
    [
        ({"current_password": "Sai@1234", "new_password": NEW_PASSWORD}, 401, "invalid_credentials", None),
        ({"current_password": SEED_PASSWORD, "new_password": "abcdefgh"}, 422, "validation_error", "new_password"),
        ({"new_password": NEW_PASSWORD}, 422, "validation_error", "current_password"),
    ],
    ids=["wrong_current_password", "weak_new_password", "missing_current_password"],
)
async def test_change_password_invalid_request_returns_error_and_keeps_password_and_tokens(
    client: AsyncClient, db: AsyncSession, auth_headers, payload: dict, status: int, code: str, field: str | None
):
    headers = await auth_headers("demo")
    password_before = await _password_state(db, DEMO_ID)
    active_before = await _user_tokens(db, DEMO_ID, revoked=False)
    assert _sha256(DEMO_REFRESH) in {token_hash for token_hash, _, _ in active_before.values()}

    res = await client.patch(CHANGE_PASSWORD, json=payload, headers=headers)

    error = _assert_error(res, status, code)
    assert isinstance(error["message"], str) and error["message"]
    if field is not None:
        assert field in [d["field"] for d in error["details"]], error["details"]
    for value in payload.values():
        assert value not in res.text, "lỗi không được phản hồi lại mật khẩu"

    # Không đổi gì: hash, password_changed_at, token chưa thu hồi
    assert await _password_state(db, DEMO_ID) == password_before
    assert await _user_tokens(db, DEMO_ID, revoked=False) == active_before
    assert (await _token_row(db, DEMO_REFRESH)).revoked_at is None
    login = await client.post(LOGIN, json=_login_body("demo"))
    assert login.status_code == 200, login.text


async def test_change_password_oauth_only_account_returns_401_invalid_credentials(
    client: AsyncClient, db: AsyncSession
):
    """Tài khoản chỉ OAuth (`password_hash = NULL`) không đổi được mật khẩu ở đây (doc 04 §4.7)."""
    # oauth@ không đăng nhập bằng mật khẩu được → tự cấp access token hợp lệ cho …15 để gọi endpoint.
    token = create_access_token(user_id=uuid.UUID(OAUTH_ID), roles=["user"], device_id=uuid.uuid4())
    headers = {"Authorization": f"Bearer {token}"}
    password_before = await _password_state(db, OAUTH_ID)
    assert password_before[0] is None

    res = await client.patch(
        CHANGE_PASSWORD, json={"current_password": SEED_PASSWORD, "new_password": NEW_PASSWORD}, headers=headers
    )

    _assert_error(res, 401, "invalid_credentials")
    assert await _password_state(db, OAUTH_ID) == password_before


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("POST", LOGOUT_ALL, None),
        ("PATCH", CHANGE_PASSWORD, {"current_password": SEED_PASSWORD, "new_password": NEW_PASSWORD}),
    ],
    ids=["logout_all", "change_password"],
)
async def test_logout_all_and_change_password_without_token_return_401_token_invalid(
    client: AsyncClient, db: AsyncSession, method: str, path: str, payload: dict | None
):
    password_before = await _password_state(db, DEMO_ID)
    active_before = await _user_tokens(db, DEMO_ID, revoked=False)

    res = await client.request(method, path, json=payload)

    _assert_error(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"
    assert await _password_state(db, DEMO_ID) == password_before
    assert await _user_tokens(db, DEMO_ID, revoked=False) == active_before


# ---------------------------------------------------------------------------
# AUTH-12, AUTH-13: PATCH /auth/me (spec docs/features/auth-users.md §5)
# ---------------------------------------------------------------------------

NEWBIE_PROFILE_SEED = ("Mai", "Đỗ Ngọc Mai", "vi-VN", "Asia/Ho_Chi_Minh", "metric")
_LONG_DISPLAY_NAME = "M" * 51


async def _profile_row(db: AsyncSession, user_id: str) -> tuple:
    """
    (display_name, full_name, locale, timezone, unit_system, updated_at) đọc thẳng từ `auth.user_profiles`.
    Truy vấn cột nên không dính identity map.
    """
    row = (
        await db.execute(
            select(
                UserProfile.display_name,
                UserProfile.full_name,
                UserProfile.locale,
                UserProfile.timezone,
                UserProfile.unit_system,
                UserProfile.updated_at,
            ).where(UserProfile.user_id == uuid.UUID(user_id))
        )
    ).one()
    return tuple(row)


@pytest.mark.tc("AUTH-12")
async def test_patch_me_partial_body_updates_only_sent_fields_and_null_clears_full_name(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    headers = await auth_headers("newbie")
    me_before = await client.get(ME, headers=headers)
    assert me_before.status_code == 200, me_before.text
    before = me_before.json()
    assert before["id"] == NEWBIE_ID
    assert before["full_name"] == "Đỗ Ngọc Mai"
    assert before["locale"] == "vi-VN"
    row_before = await _profile_row(db, NEWBIE_ID)
    assert row_before[:5] == NEWBIE_PROFILE_SEED

    # Lần 1: chỉ đổi display_name, unit_system, timezone
    first = await client.patch(
        ME, json={"display_name": "Mai Đỗ", "unit_system": "imperial", "timezone": "Asia/Tokyo"}, headers=headers
    )

    assert first.status_code == 200, first.text
    first_body = first.json()
    assert set(first_body) == set(before) == set(MeResponse.model_fields)
    assert first_body["id"] == NEWBIE_ID
    assert first_body["display_name"] == "Mai Đỗ"
    assert first_body["unit_system"] == "imperial"
    assert first_body["timezone"] == "Asia/Tokyo"
    assert first_body["full_name"] == "Đỗ Ngọc Mai"
    assert first_body["locale"] == "vi-VN"
    # Các field còn lại (email, status, roles, permissions…) giữ nguyên
    assert first_body == {**before, "display_name": "Mai Đỗ", "unit_system": "imperial", "timezone": "Asia/Tokyo"}

    row_first = await _profile_row(db, NEWBIE_ID)
    assert row_first[:5] == ("Mai Đỗ", "Đỗ Ngọc Mai", "vi-VN", "Asia/Tokyo", "imperial")
    # updated_at do trigger trg_set_updated_at của DB gán
    assert row_first[5] != row_before[5]

    # Lần 2: gửi null cho full_name → xoá giá trị, field khác giữ nguyên
    second = await client.patch(ME, json={"full_name": None}, headers=headers)

    assert second.status_code == 200, second.text
    second_body = second.json()
    assert "full_name" in second_body
    assert second_body["full_name"] is None
    assert second_body["display_name"] == "Mai Đỗ"
    assert second_body == {**first_body, "full_name": None}
    row_second = await _profile_row(db, NEWBIE_ID)
    assert row_second[:5] == ("Mai Đỗ", None, "vi-VN", "Asia/Tokyo", "imperial")

    # GET /auth/me sau đó trả đúng các giá trị đã lưu
    me_after = await client.get(ME, headers=headers)
    assert me_after.status_code == 200, me_after.text
    assert me_after.json() == second_body


@pytest.mark.tc("AUTH-13")
@pytest.mark.parametrize(
    ("payload", "expected_field"),
    [
        ({"display_name": "   "}, "display_name"),
        ({"display_name": _LONG_DISPLAY_NAME}, "display_name"),
        ({"display_name": None}, "display_name"),
        ({"locale": "vietnamese"}, "locale"),
        ({"timezone": "Mars/Olympus"}, "timezone"),
        ({"unit_system": "stone"}, "unit_system"),
        ({"email": "x@y.z"}, "email"),
    ],
    ids=[
        "display_name_blank",
        "display_name_51_chars",
        "display_name_null",
        "locale_bad_format",
        "timezone_unknown",
        "unit_system_unknown",
        "extra_field_email",
    ],
)
async def test_patch_me_invalid_body_returns_422_validation_error_and_keeps_profile(
    client: AsyncClient, db: AsyncSession, auth_headers, payload: dict, expected_field: str
):
    if payload.get("display_name") == _LONG_DISPLAY_NAME:
        assert len(_LONG_DISPLAY_NAME) == 51
    headers = await auth_headers("newbie")
    row_before = await _profile_row(db, NEWBIE_ID)
    assert row_before[:5] == NEWBIE_PROFILE_SEED

    res = await client.patch(ME, json=payload, headers=headers)

    error = _assert_error(res, 422, "validation_error")
    assert isinstance(error["message"], str) and error["message"]
    assert expected_field in [d["field"] for d in error["details"]], error["details"]
    if expected_field == "timezone":
        # Định dạng hợp lệ nên Pydantic không chặn: lỗi đến từ kiểm tra pg_catalog.pg_timezone_names ở service
        unknown = await db.scalar(
            text("SELECT count(*) FROM pg_catalog.pg_timezone_names WHERE name = :name"), {"name": "Mars/Olympus"}
        )
        assert unknown == 0
        assert [(d["field"], d["code"]) for d in error["details"]] == [("timezone", "value_error")]
    assert await _profile_row(db, NEWBIE_ID) == row_before


@pytest.mark.parametrize("field", ["locale", "timezone", "unit_system", "display_name"])
async def test_patch_me_null_for_required_profile_field_returns_422_with_that_field(
    client: AsyncClient, db: AsyncSession, auth_headers, field: str
):
    """Cột NOT NULL trong `auth.user_profiles`: gửi null bị chặn ở validation, không để lỗi ràng buộc DB."""
    headers = await auth_headers("newbie")
    row_before = await _profile_row(db, NEWBIE_ID)

    res = await client.patch(ME, json={field: None}, headers=headers)

    error = _assert_error(res, 422, "validation_error")
    assert [d["field"] for d in error["details"]] == [field]
    assert await _profile_row(db, NEWBIE_ID) == row_before


async def test_patch_me_empty_body_returns_200_current_profile_without_update(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    headers = await auth_headers("newbie")
    me = await client.get(ME, headers=headers)
    assert me.status_code == 200, me.text
    row_before = await _profile_row(db, NEWBIE_ID)

    res = await client.patch(ME, json={}, headers=headers)

    assert res.status_code == 200, res.text
    assert res.json() == me.json()
    # Không có UPDATE nào: kể cả updated_at cũng không đổi
    assert await _profile_row(db, NEWBIE_ID) == row_before


async def test_patch_me_padded_display_name_and_valid_locale_stores_stripped_values(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    headers = await auth_headers("newbie")
    display_name = "Đ" * 50

    res = await client.patch(
        ME, json={"display_name": f"  {display_name}  ", "locale": "en-US", "full_name": "Mai"}, headers=headers
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["display_name"] == display_name
    assert body["locale"] == "en-US"
    assert body["full_name"] == "Mai"
    row = await _profile_row(db, NEWBIE_ID)
    assert row[:5] == (display_name, "Mai", "en-US", "Asia/Ho_Chi_Minh", "metric")


async def test_patch_me_without_token_returns_401_token_invalid(client: AsyncClient, db: AsyncSession):
    row_before = await _profile_row(db, NEWBIE_ID)

    res = await client.patch(ME, json={"display_name": "Mai Đỗ"})

    _assert_error(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"
    assert await _profile_row(db, NEWBIE_ID) == row_before


async def test_patch_me_profile_missing_returns_404_user_not_found(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    """Dữ liệu hỏng (user không có `user_profiles`): báo `user_not_found`, không tạo hồ sơ mới."""
    headers = await auth_headers("newbie")
    # Xoá trong transaction ngoài của test (bị rollback cuối test); ORM delete cũng gỡ đối tượng khỏi identity map.
    # commit ở đây chỉ release savepoint (conftest), để lần rollback savepoint khi request lỗi không hoàn tác lệnh xoá.
    await db.execute(delete(UserProfile).where(UserProfile.user_id == uuid.UUID(NEWBIE_ID)))
    await db.commit()

    res = await client.patch(ME, json={"display_name": "Mai Đỗ"}, headers=headers)

    _assert_error(res, 404, "user_not_found")
    count = await db.scalar(
        select(func.count()).select_from(UserProfile).where(UserProfile.user_id == uuid.UUID(NEWBIE_ID))
    )
    assert count == 0
