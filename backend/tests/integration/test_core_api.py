"""Integration test phần core: health, xử lý lỗi, phân quyền, cache quyền Redis, enum khớp DB, log."""

import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, Query
from httpx import ASGITransport, AsyncClient
from jose import jwt
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user, require_permission
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.redis_client import get_redis
from app.core.security import create_access_token
from app.main import app, create_app
from app.models import enums
from app.services import health_service, permission_service
from tests.conftest import persona_id

REQUEST_ID = re.compile(r"^req_[0-9a-f]{8}$")


def _err(res, status: int, code: str) -> dict:
    assert res.status_code == status, res.text
    body = res.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert set(body["error"]) == {"code", "message", "details", "request_id"}
    return body["error"]


@pytest.fixture
async def test_client(db: AsyncSession):
    """App riêng từ create_app() + route chỉ dùng trong test; dùng chung session rollback của `db`."""
    test_app = create_app()

    @test_app.get("/_t/limit")
    async def _limit(limit: int = Query(20, ge=1, le=100)) -> dict:
        return {"limit": limit}

    @test_app.get("/_t/raise/{kind}")
    async def _raise(kind: str) -> dict:
        if kind == "not-found":
            raise NotFoundError("user_not_found", "Người dùng không tồn tại")
        if kind == "conflict":
            raise ConflictError("email_already_exists", "Email đã được sử dụng")
        if kind == "bad-request":
            raise BadRequestError()
        raise RuntimeError("SELECT secret FROM x")

    @test_app.post("/_t/roles/{code}")
    async def _insert_role(code: str, session: AsyncSession = Depends(get_db)) -> dict:
        await session.execute(text("INSERT INTO auth.roles (code, name) VALUES (:c, 'x')"), {"c": code})
        await session.flush()
        return {"ok": True}

    @test_app.get("/_t/protected")
    async def _protected(current: CurrentUser = Depends(get_current_user)) -> dict:
        return {"id": str(current.id)}

    @test_app.get("/_t/needs-perm")
    async def _needs_perm(current: CurrentUser = Depends(require_permission("exercise", "create"))) -> dict:
        return {"id": str(current.id)}

    test_app.dependency_overrides[get_db] = app.dependency_overrides[get_db]
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# --- Health ---
async def test_health_all_up(client: AsyncClient, monkeypatch):
    async def ai_up() -> bool:
        return True

    monkeypatch.setattr(health_service, "_check_ai_service", ai_up)
    res = await client.get("/api/v1/health")
    assert res.status_code == 200, res.text
    body = res.json()
    assert {k: body[k] for k in ("database", "redis", "ai_service")} == {"database": "up", "redis": "up", "ai_service": "up"}
    assert body["checked_at"].endswith("Z")
    assert "status" not in body and "success" not in body
    assert REQUEST_ID.match(res.headers["X-Request-ID"])


async def test_health_ai_down_is_degraded(client: AsyncClient, monkeypatch):
    async def ai_down() -> bool:
        return False

    monkeypatch.setattr(health_service, "_check_ai_service", ai_down)
    body = (await client.get("/api/v1/health")).json()
    assert body["ai_service"] == "degraded" and body["database"] == "up" and body["redis"] == "up"


async def test_health_redis_down_returns_503(client: AsyncClient, monkeypatch):
    async def down() -> bool:
        return False

    monkeypatch.setattr(health_service, "_check_redis", down)
    monkeypatch.setattr(health_service, "_check_ai_service", down)
    error = _err(await client.get("/api/v1/health"), 503, "service_unavailable")
    assert [d["field"] for d in error["details"]] == ["redis"]


async def test_health_real_ai_service_unreachable_is_degraded(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "AI_SERVICE_URL", "http://127.0.0.1:9")  # cổng discard: không có dịch vụ
    assert (await client.get("/api/v1/health")).json()["ai_service"] == "degraded"


# --- Lỗi framework & request id ---
async def test_framework_errors_use_error_format(client: AsyncClient):
    _err(await client.get("/api/v1/khong-ton-tai"), 404, "http_404")
    error = _err(await client.post("/api/v1/health"), 405, "http_405")
    assert error["details"] == []
    _err(await client.get("/health"), 404, "http_404")  # health chỉ còn dưới /api/v1


async def test_request_id_echo_and_generated(client: AsyncClient):
    res = await client.get("/api/v1/khong-ton-tai", headers={"X-Request-ID": "req_1a2b3c4d"})
    assert res.headers["X-Request-ID"] == "req_1a2b3c4d"
    assert res.json()["error"]["request_id"] == "req_1a2b3c4d"
    res = await client.get("/api/v1/khong-ton-tai")
    assert REQUEST_ID.match(res.headers["X-Request-ID"])
    assert res.json()["error"]["request_id"] == res.headers["X-Request-ID"]


async def test_validation_error_details(test_client: AsyncClient):
    error = _err(await test_client.get("/_t/limit?limit=101"), 422, "validation_error")
    assert error["details"][0]["field"] == "limit"
    assert all(set(d) == {"field", "message", "code"} for d in error["details"])


async def test_app_exception_subclasses(test_client: AsyncClient):
    error = _err(await test_client.get("/_t/raise/not-found"), 404, "user_not_found")
    assert error["message"] == "Người dùng không tồn tại" and error["details"] == []
    _err(await test_client.get("/_t/raise/conflict"), 409, "email_already_exists")
    _err(await test_client.get("/_t/raise/bad-request"), 400, "bad_request")


async def test_unhandled_exception_hides_internals(test_client: AsyncClient):
    res = await test_client.get("/_t/raise/boom")
    _err(res, 500, "internal_error")
    assert not any(word in res.text for word in ("RuntimeError", "SELECT", "Traceback"))


async def test_integrity_errors_are_translated(test_client: AsyncClient):
    res = await test_client.post("/_t/roles/admin")  # uq_roles_code
    _err(res, 409, "conflict")
    assert "INSERT" not in res.text and "auth.roles" not in res.text
    res = await test_client.post("/_t/roles/Bad Code")  # ck_roles_code_format
    error = _err(res, 422, "validation_error")
    assert error["details"][0]["code"] == "constraint_violation"
    assert "ck_roles" not in res.text


# --- Xác thực & phân quyền ---
def _token(**overrides) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": persona_id(3), "roles": ["user"], "did": str(uuid.uuid4()), "type": "access",
        "iat": int(now.timestamp()), "exp": int((now + timedelta(minutes=5)).timestamp()), "jti": str(uuid.uuid4()),
    }
    payload.update(overrides)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


async def test_get_current_user_rejects_bad_tokens(test_client: AsyncClient):
    past = int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp())
    _err(await test_client.get("/_t/protected", headers={"Authorization": f"Bearer {_token(exp=past)}"}), 401, "token_expired")
    for bad in (_token(type="refresh"), _token() + "x", "abc.def"):
        _err(await test_client.get("/_t/protected", headers={"Authorization": f"Bearer {bad}"}), 401, "token_invalid")
    res = await test_client.get("/_t/protected")
    _err(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"


async def test_get_current_user_rejects_inactive_users(test_client: AsyncClient):
    for nn in (11, 13, 14):  # pending, disabled, deleted
        token = create_access_token(user_id=uuid.UUID(persona_id(nn)), roles=["user"], device_id=uuid.uuid4())
        _err(await test_client.get("/_t/protected", headers={"Authorization": f"Bearer {token}"}), 401, "token_invalid")
    token = create_access_token(user_id=uuid.uuid4(), roles=["user"], device_id=uuid.uuid4())
    _err(await test_client.get("/_t/protected", headers={"Authorization": f"Bearer {token}"}), 401, "token_invalid")


async def test_require_permission(test_client: AsyncClient, auth_headers):
    res = await test_client.get("/_t/protected", headers=await auth_headers("demo"))
    assert res.status_code == 200 and res.json()["id"] == persona_id(3)
    for persona in ("demo", "trainer"):  # trainer: content_editor đã hết hạn
        _err(await test_client.get("/_t/needs-perm", headers=await auth_headers(persona)), 403, "permission_denied")
    for persona in ("editor", "admin"):
        assert (await test_client.get("/_t/needs-perm", headers=await auth_headers(persona))).status_code == 200
    _err(await test_client.get("/_t/needs-perm"), 401, "token_invalid")


# --- Cache quyền trên Redis ---
async def test_permission_cache_written_and_reused(db: AsyncSession):
    editor = uuid.UUID(persona_id(2))
    redis = get_redis()
    key = permission_service.cache_key(editor)
    await redis.delete(key)
    try:
        perms = await permission_service.get_permissions(db, editor)
        assert "exercise:create" in perms and "workout:manage_own" not in perms
        assert 0 < await redis.ttl(key) <= get_settings().PERMISSION_CACHE_TTL_SECONDS
        assert set(json.loads(await redis.get(key))) == perms
        assert await permission_service.get_permissions(db, editor) == perms
        await permission_service.invalidate_permissions(editor)
        assert await redis.exists(key) == 0
    finally:
        await redis.delete(key)


async def test_permission_falls_back_to_db_when_redis_down(db: AsyncSession, monkeypatch):
    class BrokenRedis:
        async def get(self, *_):
            raise RedisConnectionError("down")

        async def set(self, *_, **__):
            raise RedisConnectionError("down")

    monkeypatch.setattr(permission_service, "get_redis", lambda: BrokenRedis())
    perms = await permission_service.get_permissions(db, uuid.UUID(persona_id(3)))
    assert "workout:manage_own" in perms


# --- Enum khớp DB (doc 05 §2.3) ---
ENUM_TYPES = {
    enums.UserStatus: "auth.user_status", enums.UnitSystem: "auth.unit_system",
    enums.DevicePlatform: "auth.device_platform", enums.TokenRevokeReason: "auth.token_revoke_reason",
    enums.LoginFailureReason: "auth.login_failure_reason", enums.ContentStatus: "catalog.content_status",
    enums.ExerciseCategory: "catalog.exercise_category", enums.MechanicType: "catalog.mechanic_type",
    enums.ForceType: "catalog.force_type", enums.MuscleRole: "catalog.muscle_role",
    enums.MediaRole: "catalog.media_role", enums.JointType: "catalog.joint_type", enums.Gender: "body.gender",
    enums.MeasurementSource: "body.measurement_source", enums.GoalStatus: "body.goal_status",
    enums.PlanStatus: "training.plan_status", enums.ScheduleStatus: "training.schedule_status",
    enums.SessionStatus: "training.session_status", enums.SetType: "training.set_type",
    enums.LogSource: "training.log_source", enums.AddedVia: "training.added_via",
    enums.AnalysisMode: "ai.analysis_mode", enums.IssueSeverity: "ai.issue_severity",
    enums.ScanFeedback: "ai.scan_feedback", enums.JobStatus: "util.job_status",
    enums.StorageProvider: "media.storage_provider", enums.MediaStatus: "media.media_status",
    enums.PhotoAngle: "media.photo_angle", enums.CaptureSource: "media.capture_source",
    enums.ReportType: "analytics.report_type",
}


async def test_enums_match_database(db: AsyncSession):
    for enum_cls, qualified in ENUM_TYPES.items():
        schema, name = qualified.split(".")
        rows = await db.execute(
            text(
                "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
                "JOIN pg_namespace n ON n.oid = t.typnamespace WHERE n.nspname = :s AND t.typname = :t"
            ),
            {"s": schema, "t": name},
        )
        assert {r[0] for r in rows} == {m.value for m in enum_cls}, qualified
    roles = {r[0] for r in await db.execute(text("SELECT code FROM auth.roles"))}
    assert roles == {m.value for m in enums.RoleCode}


# --- Log JSON ---
async def test_access_log_is_json_without_secrets(client: AsyncClient, auth_headers, caplog):
    headers = await auth_headers("demo")
    caplog.set_level(logging.INFO, logger="app.access")
    caplog.clear()
    res = await client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    records = [r for r in caplog.records if r.name == "app.access"]
    assert len(records) == 1
    entry = json.loads(records[0].getMessage())
    assert set(entry) == {"timestamp", "level", "request_id", "method", "path", "status", "duration_ms", "user_id"}
    assert entry["status"] == 200 and entry["user_id"] == persona_id(3)
    token = headers["Authorization"].split()[1]
    assert all(token not in r.getMessage() for r in caplog.records)
