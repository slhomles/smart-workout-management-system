"""Integration test /auth trên PostgreSQL thật (persona seed, xem docs/database/test-dataset.md)."""

from httpx import AsyncClient

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
