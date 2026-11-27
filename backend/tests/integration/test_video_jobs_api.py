"""Integration test /ai/video-jobs (chức năng 6, luồng video 1B) trên PostgreSQL thật.

Helper ở đầu file theo "Quy ước chung" của spec set-rep-tempo §5, dùng lại cho các test GET/worker.
Dữ liệu tạo trong test được `db.commit()` (chỉ release savepoint của fixture `db`), để lỗi ở một
request không cuốn theo dữ liệu đã chuẩn bị; cuối test fixture vẫn rollback toàn bộ.
"""

import uuid
from datetime import datetime
from typing import Any

import httpx
import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, DataValidationError, NotFoundError
from app.schemas.base import encode_cursor
from app.schemas.video_job import VideoJobFailureRequest
from app.services import video_job_service

BASE = "/api/v1/ai/video-jobs"
SQUAT_SLUG = "barbell-back-squat"

KEYS_VJ = {
    "id", "pose_analysis_id", "set_id", "session_id", "exercise_id", "exercise_name", "status",
    "source_video_media_id", "result_video_media_id", "model_name", "model_version", "overall_score",
    "correct_form_pct", "detected_rep_count", "feedback_summary", "queued_at", "started_at", "finished_at",
    "analyzed_at", "created_at",
}

_SET_SQL = """
SELECT es.id AS set_id, se.session_id, es.session_exercise_id, s.started_at
FROM training.exercise_sets es
JOIN training.session_exercises se ON se.id = es.session_exercise_id
JOIN training.workout_sessions s ON s.id = se.session_id
JOIN catalog.exercises e ON e.id = se.exercise_id
JOIN auth.users u ON u.id = s.user_id
WHERE u.email = :email AND {condition}
ORDER BY s.started_at DESC, se.order_no, es.set_no, es.id
"""


# --- Đọc dữ liệu seed qua db ---
def _email(persona: str) -> str:
    return f"{persona}@smartworkout.local"


async def persona_user_id(db: AsyncSession, persona: str) -> uuid.UUID:
    """UUID của persona seed (đọc qua db, không hard-code)."""
    found = await db.scalar(text("SELECT id FROM auth.users WHERE email = :email"), {"email": _email(persona)})
    assert found is not None, persona
    return found


async def _set_rows(db: AsyncSession, persona: str, condition: str) -> list[dict[str, Any]]:
    rows = await db.execute(text(_SET_SQL.format(condition=condition)), {"email": _email(persona)})
    return [dict(r) for r in rows.mappings().all()]


async def squat_sets(db: AsyncSession) -> list[dict[str, Any]]:
    """[S1, S2]: hiệp set_no=1 bài squat trong buổi (chưa xoá) mới nhất / thứ 2 của demo; có session_id, session_exercise_id."""
    rows = await _set_rows(db, "demo", f"e.slug = '{SQUAT_SLUG}' AND es.set_no = 1 AND s.deleted_at IS NULL")
    by_session: dict[uuid.UUID, dict[str, Any]] = {}
    for row in rows:
        by_session.setdefault(row["session_id"], row)
    picked = list(by_session.values())[:2]
    assert len(picked) == 2, "seed demo cần ≥ 2 buổi có squat"
    return picked


async def _first_set_id(db: AsyncSession, persona: str, condition: str) -> int:
    rows = await _set_rows(db, persona, condition)
    assert rows, f"không có hiệp seed: {persona} / {condition}"
    return int(rows[0]["set_id"])


async def hammer_set(db: AsyncSession) -> int:
    """HAMMER: hiệp hammer-curl (supports_ai_tracking=false) của demo, buổi chưa xoá."""
    return await _first_set_id(db, "demo", "e.slug = 'hammer-curl' AND s.deleted_at IS NULL")


async def power_set(db: AsyncSession) -> int:
    """POWER_SET: hiệp của power, buổi chưa xoá, bài hỗ trợ AI."""
    return await _first_set_id(db, "power", "e.supports_ai_tracking AND s.deleted_at IS NULL")


async def deleted_set(db: AsyncSession) -> int:
    """DELETED_SET: hiệp push-up trong buổi đã xoá mềm "Buổi nhập nhầm" của inprogress."""
    condition = "e.slug = 'push-up' AND s.deleted_at IS NOT NULL AND s.name = 'Buổi nhập nhầm'"
    return await _first_set_id(db, "inprogress", condition)


async def trainer_set(db: AsyncSession) -> int:
    """TRAINER_SET: hiệp barbell-back-squat của trainer."""
    return await _first_set_id(db, "trainer", f"e.slug = '{SQUAT_SLUG}' AND s.deleted_at IS NULL")


async def squat_exercise(db: AsyncSession) -> tuple[int, str]:
    """(SQUAT_ID, SQUAT_NAME)."""
    row = (await db.execute(text("SELECT id, name FROM catalog.exercises WHERE slug = :s"), {"s": SQUAT_SLUG})).one()
    return int(row.id), str(row.name)


async def img_demo(db: AsyncSession) -> uuid.UUID:
    """IMG_DEMO: ảnh tiến độ seed của demo (image/jpeg, available)."""
    sql = "SELECT id FROM media.media_files WHERE object_key = 'users/demo/progress/w00-front.jpg'"
    found = await db.scalar(text(sql))
    assert found is not None
    return found


# --- Tạo dữ liệu test ---
async def make_video(
    db: AsyncSession, owner: uuid.UUID | None, status: str = "available", mime: str = "video/mp4"
) -> uuid.UUID:
    """VID(owner, status, mime) của spec §5; object_key có uuid4 để không đụng uq_media_files_object."""
    sql = """
    INSERT INTO media.media_files (uploaded_by_user_id, bucket, object_key, mime_type, size_bytes,
                                   checksum_sha256, status, deleted_at)
    VALUES (:owner, 'smart-workout-media', :key, :mime, 1000, repeat('a', 64),
            CAST(:status AS media.media_status), NULL)
    RETURNING id
    """
    params = {"owner": owner, "key": f"tests/srt/{uuid.uuid4()}.mp4", "mime": mime, "status": status}
    media_id = await db.scalar(text(sql), params)
    await db.commit()
    return media_id


async def make_deleted_video(db: AsyncSession, owner: uuid.UUID | None) -> uuid.UUID:
    """VID(owner, deleted=True): video available nhưng đã xoá mềm."""
    media_id = await make_video(db, owner)
    await db.execute(text("UPDATE media.media_files SET deleted_at = now() WHERE id = :id"), {"id": media_id})
    await db.commit()
    return media_id


async def count_ai_rows(db: AsyncSession) -> tuple[int, int]:
    """(số dòng ai.pose_analyses, số dòng ai.video_analysis_jobs)."""
    sql = "SELECT (SELECT count(*) FROM ai.pose_analyses), (SELECT count(*) FROM ai.video_analysis_jobs)"
    row = (await db.execute(text(sql))).one()
    return int(row[0]), int(row[1])


async def set_snapshot(db: AsyncSession, set_id: int) -> tuple[Any, ...]:
    """(reps, source, updated_at, weight_kg) của hiệp, để kiểm hiệp không đổi."""
    sql = "SELECT reps, source::text, updated_at, weight_kg FROM training.exercise_sets WHERE id = :id"
    return tuple((await db.execute(text(sql), {"id": set_id})).one())


async def rep_event_count(db: AsyncSession, set_id: int) -> int:
    """Số dòng training.set_rep_events của hiệp."""
    sql = "SELECT count(*) FROM training.set_rep_events WHERE set_id = :id"
    return int(await db.scalar(text(sql), {"id": set_id}))


async def post_job(client: AsyncClient, headers: dict[str, str], set_id: Any, media: Any) -> Response:
    """POST J(set, media)."""
    body = {"set_id": set_id, "source_video_media_id": str(media) if media is not None else None}
    return await client.post(BASE, json=body, headers=headers)


def assert_error(res: Response, status: int, code: str) -> dict[str, Any]:
    """Body lỗi có đúng một key `error` gồm code/message/details/request_id; trả `error`."""
    assert res.status_code == status, res.text
    body = res.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details", "request_id"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["details"], list)
    return body["error"]


def assert_job_created(res: Response) -> dict[str, Any]:
    """202 + Location đúng id + body đúng KEYS-VJ, không envelope; trả body."""
    assert res.status_code == 202, res.text
    body = res.json()
    assert set(body) == KEYS_VJ
    assert res.headers["Location"] == f"{BASE}/{body['id']}"
    return body


_UUID_KEYS = ("id", "pose_analysis_id", "session_id", "source_video_media_id", "result_video_media_id")
_INT_KEYS = ("set_id", "exercise_id", "detected_rep_count")
_TIME_KEYS = ("queued_at", "started_at", "finished_at", "analyzed_at", "created_at")


def _non_null(body: dict[str, Any], keys: tuple[str, ...]) -> list[Any]:
    return [body[key] for key in keys if body[key] is not None]


def assert_job_json_types(body: dict[str, Any]) -> None:
    """Kiểu JSON theo spec §5: UUID chuỗi, số nguyên JSON, thời điểm ISO kết thúc `Z` (hoặc null)."""
    assert all(str(uuid.UUID(v)) == v for v in _non_null(body, _UUID_KEYS)), body
    assert all(type(v) is int for v in _non_null(body, _INT_KEYS)), body
    assert all(isinstance(v, str) and v.endswith("Z") for v in _non_null(body, _TIME_KEYS)), body


# --- SRT-01 ---
@pytest.mark.tc("SRT-01")
async def test_create_job_own_set_returns_queued_job(client: AsyncClient, auth_headers, db: AsyncSession):
    s1 = (await squat_sets(db))[0]
    squat_id, squat_name = await squat_exercise(db)
    v_demo = await make_video(db, await persona_user_id(db, "demo"))
    before = await set_snapshot(db, s1["set_id"])

    body = assert_job_created(await post_job(client, await auth_headers("demo"), s1["set_id"], v_demo))

    expected = {
        "status": "queued", "set_id": s1["set_id"], "session_id": str(s1["session_id"]),
        "exercise_id": squat_id, "exercise_name": squat_name,
        "source_video_media_id": str(v_demo), "result_video_media_id": None,
        "model_name": "yolov8_pose", "model_version": "8.2.0",
        "overall_score": None, "correct_form_pct": None, "detected_rep_count": None, "feedback_summary": None,
        "started_at": None, "finished_at": None, "analyzed_at": None,
    }
    assert {key: body[key] for key in expected} == expected
    assert_job_json_types(body)
    assert body["queued_at"] is not None and body["created_at"] is not None
    await _assert_job_rows(db, body, s1["set_id"])
    assert await set_snapshot(db, s1["set_id"]) == before
    assert await rep_event_count(db, s1["set_id"]) == 0


async def _assert_job_rows(db: AsyncSession, body: dict[str, Any], set_id: int) -> None:
    analysis_sql = "SELECT mode::text, set_id, analyzed_at FROM ai.pose_analyses WHERE id = :id"
    analyses = (await db.execute(text(analysis_sql), {"id": body["pose_analysis_id"]})).all()
    assert [tuple(r) for r in analyses] == [("video_server", set_id, None)]
    job_sql = """
    SELECT status::text, priority, attempt_count, worker_id, pose_analysis_id
    FROM ai.video_analysis_jobs WHERE id = :id
    """
    jobs = (await db.execute(text(job_sql), {"id": body["id"]})).all()
    assert [tuple(r) for r in jobs] == [("queued", 5, 0, None, uuid.UUID(body["pose_analysis_id"]))]


# --- SRT-02 ---
@pytest.mark.tc("SRT-02")
async def test_create_job_repeated_and_reused_video_creates_new_jobs(
    client: AsyncClient, auth_headers, db: AsyncSession
):
    s1, s2 = await squat_sets(db)
    v_demo = await make_video(db, await persona_user_id(db, "demo"))
    headers = await auth_headers("demo")

    first = assert_job_created(await post_job(client, headers, s1["set_id"], v_demo))
    second = assert_job_created(await post_job(client, headers, s1["set_id"], v_demo))
    assert first["id"] != second["id"]
    assert first["pose_analysis_id"] != second["pose_analysis_id"]
    sql = """
    SELECT count(*) FROM ai.video_analysis_jobs j JOIN ai.pose_analyses pa ON pa.id = j.pose_analysis_id
    WHERE pa.set_id = :set_id
    """
    assert await db.scalar(text(sql), {"set_id": s1["set_id"]}) == 2

    other = assert_job_created(await post_job(client, headers, s2["set_id"], v_demo))
    assert other["set_id"] == s2["set_id"] and other["session_id"] == str(s2["session_id"])
    assert other["source_video_media_id"] == str(v_demo)


# --- SRT-03 ---
@pytest.mark.tc("SRT-03")
async def test_create_job_invalid_body_returns_validation_error(
    client: AsyncClient, auth_headers, db: AsyncSession
):
    s1 = (await squat_sets(db))[0]
    v_demo = await make_video(db, await persona_user_id(db, "demo"))
    valid = {"set_id": s1["set_id"], "source_video_media_id": str(v_demo)}
    cases: list[tuple[dict[str, Any], str]] = [
        ({"source_video_media_id": str(v_demo)}, "set_id"),
        ({**valid, "set_id": "abc"}, "set_id"),
        ({**valid, "set_id": 0}, "set_id"),
        ({**valid, "set_id": 9223372036854775808}, "set_id"),
        ({"set_id": s1["set_id"]}, "source_video_media_id"),
        ({**valid, "source_video_media_id": "khong-phai-uuid"}, "source_video_media_id"),
    ]
    headers = await auth_headers("demo")
    before = await count_ai_rows(db)
    for body, field in cases:
        error = assert_error(await client.post(BASE, json=body, headers=headers), 422, "validation_error")
        assert field in [d["field"] for d in error["details"]], (body, error)
    assert await count_ai_rows(db) == before


# --- SRT-04 ---
@pytest.mark.tc("SRT-04")
async def test_create_job_business_rule_violation_returns_validation_error(
    client: AsyncClient, auth_headers, db: AsyncSession
):
    s1 = (await squat_sets(db))[0]["set_id"]
    demo_id = await persona_user_id(db, "demo")
    v_demo = await make_video(db, demo_id)
    cases: list[tuple[int, uuid.UUID, str]] = [
        (await hammer_set(db), v_demo, "set_id"),
        (s1, await img_demo(db), "source_video_media_id"),
        (s1, await make_video(db, demo_id, status="pending_upload"), "source_video_media_id"),
        (s1, await make_deleted_video(db, demo_id), "source_video_media_id"),
        (s1, await make_video(db, await persona_user_id(db, "power")), "source_video_media_id"),
        (s1, uuid.uuid4(), "source_video_media_id"),
    ]
    headers = await auth_headers("demo")
    before = await count_ai_rows(db)
    errors = []
    for set_id, media, field in cases:
        error = assert_error(await post_job(client, headers, set_id, media), 422, "validation_error")
        assert error["details"][0]["field"] == field, error
        errors.append(error)
    # Video của user khác và video không tồn tại phải giống hệt nhau (không lộ media người khác).
    assert errors[4]["message"] == errors[5]["message"]
    assert errors[4]["details"][0]["message"] == errors[5]["details"][0]["message"]
    assert await count_ai_rows(db) == before


# --- SRT-05 ---
@pytest.mark.tc("SRT-05")
async def test_create_job_set_not_owned_returns_not_found(client: AsyncClient, auth_headers, db: AsyncSession):
    demo_headers = await auth_headers("demo")
    v_demo = await make_video(db, await persona_user_id(db, "demo"))
    v_inprog = await make_video(db, await persona_user_id(db, "inprogress"))
    missing_set = int(await db.scalar(text("SELECT max(id) FROM training.exercise_sets"))) + 1000
    other_set = await power_set(db)
    before = await count_ai_rows(db)

    not_owned = assert_error(await post_job(client, demo_headers, other_set, v_demo), 404, "exercise_set_not_found")
    missing = assert_error(await post_job(client, demo_headers, missing_set, v_demo), 404, "exercise_set_not_found")
    assert not_owned["message"] == missing["message"]
    soft_deleted = await post_job(client, await auth_headers("inprogress"), await deleted_set(db), v_inprog)
    set_before_media = await post_job(client, demo_headers, other_set, uuid.uuid4())
    errors = [not_owned, missing, assert_error(soft_deleted, 404, "exercise_set_not_found"),
              assert_error(set_before_media, 404, "exercise_set_not_found")]

    s1 = (await squat_sets(db))[0]
    await db.execute(
        text("UPDATE training.workout_sessions SET deleted_at = now() WHERE id = :id"), {"id": s1["session_id"]}
    )
    await db.commit()
    errors.append(assert_error(await post_job(client, demo_headers, s1["set_id"], v_demo), 404, "exercise_set_not_found"))

    assert all(e["details"] == [] for e in errors)
    assert await count_ai_rows(db) == before


# --- Helper cho GET /ai/video-jobs ---
async def get_jobs(client: AsyncClient, headers: dict[str, str], params: dict[str, Any] | None = None) -> Response:
    """GET danh sách job video với query `params`."""
    return await client.get(BASE, params=params or {}, headers=headers)


def assert_page(res: Response) -> dict[str, Any]:
    """200 + body đúng 2 key data/pagination, mỗi phần tử đúng KEYS-VJ; trả body."""
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == {"data", "pagination"}
    assert set(body["pagination"]) == {"next_cursor", "has_more"}
    assert all(set(item) == KEYS_VJ for item in body["data"]), body
    return body


def _ids(items: list[dict[str, Any]]) -> set[str]:
    return {item["id"] for item in items}


def assert_newest_first(items: list[dict[str, Any]]) -> None:
    """Dãy (created_at, id) không tăng; so sánh theo giá trị (datetime, UUID) như ORDER BY của DB."""
    keys = [(datetime.fromisoformat(item["created_at"]), uuid.UUID(item["id"])) for item in items]
    assert keys == sorted(keys, reverse=True), keys


async def _demo_jobs(
    client: AsyncClient, auth_headers, db: AsyncSession, set_keys: tuple[int, ...]
) -> tuple[dict[str, str], list[dict[str, Any]], list[dict[str, Any]]]:
    """Demo POST J(S<k>, V_DEMO) cho từng k (0 = S1, 1 = S2); trả (headers, [S1, S2], body các job)."""
    sets = await squat_sets(db)
    v_demo = await make_video(db, await persona_user_id(db, "demo"))
    headers = await auth_headers("demo")
    jobs = [assert_job_created(await post_job(client, headers, sets[k]["set_id"], v_demo)) for k in set_keys]
    return headers, sets, jobs


# --- SRT-06 ---
@pytest.mark.tc("SRT-06")
async def test_list_jobs_own_jobs_returns_post_bodies_newest_first(
    client: AsyncClient, auth_headers, db: AsyncSession
):
    headers, _, (job_a, job_b) = await _demo_jobs(client, auth_headers, db, (0, 1))

    body = assert_page(await get_jobs(client, headers))

    assert body["pagination"] == {"next_cursor": None, "has_more": False}
    assert len(body["data"]) == 2
    assert _ids(body["data"]) == {job_a["id"], job_b["id"]}
    by_id = {item["id"]: item for item in body["data"]}
    assert by_id[job_a["id"]] == job_a
    assert by_id[job_b["id"]] == job_b
    assert_newest_first(body["data"])


# --- SRT-08 ---
@pytest.mark.tc("SRT-08")
async def test_list_jobs_limit_and_next_cursor_pages_through_all(
    client: AsyncClient, auth_headers, db: AsyncSession
):
    headers, _, jobs = await _demo_jobs(client, auth_headers, db, (0, 1, 0))

    first = assert_page(await get_jobs(client, headers, {"limit": 2}))
    assert len(first["data"]) == 2
    assert first["pagination"]["has_more"] is True
    assert isinstance(first["pagination"]["next_cursor"], str)

    params = {"limit": 2, "cursor": first["pagination"]["next_cursor"]}
    second = assert_page(await get_jobs(client, headers, params))
    assert len(second["data"]) == 1
    assert second["pagination"] == {"next_cursor": None, "has_more": False}

    merged = first["data"] + second["data"]
    assert len(_ids(merged)) == 3
    assert _ids(merged) == _ids(jobs)
    assert_newest_first(merged)


# --- SRT-09 ---
@pytest.mark.tc("SRT-09")
async def test_list_jobs_other_users_and_soft_deleted_session_are_hidden(
    client: AsyncClient, auth_headers, db: AsyncSession
):
    headers, sets, (_, job_b) = await _demo_jobs(client, auth_headers, db, (0, 1))

    for persona in ("power", "admin"):
        body = assert_page(await get_jobs(client, await auth_headers(persona)))
        assert body["data"] == [], persona
        assert body["pagination"]["has_more"] is False

    await db.execute(
        text("UPDATE training.workout_sessions SET deleted_at = now() WHERE id = :id"), {"id": sets[0]["session_id"]}
    )
    await db.commit()
    body = assert_page(await get_jobs(client, headers))
    assert _ids(body["data"]) == {job_b["id"]}


# --- SRT-10 ---
@pytest.mark.tc("SRT-10")
async def test_list_jobs_invalid_query_returns_validation_error(client: AsyncClient, auth_headers):
    cases: list[tuple[dict[str, Any], str]] = [
        ({"limit": 0}, "limit"),
        ({"limit": 101}, "limit"),
        ({"cursor": "!!!khong-phai-cursor"}, "cursor"),
        ({"cursor": encode_cursor({"foo": 1})}, "cursor"),
        ({"status": "done"}, "status"),
        ({"set_id": "abc"}, "set_id"),
    ]
    headers = await auth_headers("demo")
    for params, field in cases:
        error = assert_error(await get_jobs(client, headers, params), 422, "validation_error")
        assert field in [d["field"] for d in error["details"]], (params, error)


# --- SRT-11 ---
@pytest.mark.tc("SRT-11")
async def test_jobs_endpoints_missing_or_bad_token_returns_token_invalid(client: AsyncClient, db: AsyncSession):
    s1 = (await squat_sets(db))[0]["set_id"]
    v_demo = await make_video(db, await persona_user_id(db, "demo"))
    before = await count_ai_rows(db)
    for headers in ({}, {"Authorization": "Bearer khong-phai-jwt"}):
        for res in (await post_job(client, headers, s1, v_demo), await get_jobs(client, headers)):
            assert_error(res, 401, "token_invalid")
            assert res.headers.get("WWW-Authenticate") == "Bearer"
    assert (await count_ai_rows(db))[1] == before[1]


# --- SRT-12 ---
@pytest.mark.tc("SRT-12")
async def test_jobs_endpoints_without_ai_use_returns_permission_denied(
    client: AsyncClient, auth_headers, db: AsyncSession
):
    s1 = (await squat_sets(db))[0]["set_id"]
    v_demo = await make_video(db, await persona_user_id(db, "demo"))
    editor = await auth_headers("editor")
    before = await count_ai_rows(db)

    assert_error(await post_job(client, editor, s1, v_demo), 403, "permission_denied")
    assert_error(await get_jobs(client, editor), 403, "permission_denied")
    assert (await count_ai_rows(db))[1] == before[1]


@pytest.mark.tc("SRT-12")
async def test_jobs_endpoints_trainer_with_active_user_role_succeeds(
    client: AsyncClient, auth_headers, db: AsyncSession
):
    set_id = await trainer_set(db)
    v_trainer = await make_video(db, await persona_user_id(db, "trainer"))
    headers = await auth_headers("trainer")

    created = assert_job_created(await post_job(client, headers, set_id, v_trainer))
    assert created["set_id"] == set_id
    body = assert_page(await get_jobs(client, headers))
    assert _ids(body["data"]) == {created["id"]}


# --- SRT-13 ---
@pytest.mark.tc("SRT-13")
async def test_jobs_endpoints_make_no_outbound_http_call(
    client: AsyncClient, auth_headers, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    outbound_calls: list[httpx.Request] = []

    async def _refuse(self: httpx.AsyncHTTPTransport, request: httpx.Request) -> httpx.Response:
        outbound_calls.append(request)
        raise httpx.ConnectError("mạng ngoài bị chặn trong test", request=request)

    monkeypatch.setattr(get_settings(), "AI_SERVICE_URL", "http://127.0.0.1:9")
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _refuse)

    headers, _, (job,) = await _demo_jobs(client, auth_headers, db, (0,))
    body = assert_page(await get_jobs(client, headers))

    listed = {item["id"]: item for item in body["data"]}
    assert listed[job["id"]]["status"] == "queued"
    assert len(outbound_calls) == 0


# --- Helper cho service worker (start/result/failure) ---
async def job_state(db: AsyncSession, job_id: uuid.UUID) -> dict[str, Any]:
    """Trạng thái dòng ai.video_analysis_jobs đọc thẳng qua db (không qua ORM/identity map)."""
    sql = """
    SELECT status::text AS status, queued_at, started_at, finished_at, attempt_count, max_attempts,
           worker_id, error_message
    FROM ai.video_analysis_jobs WHERE id = :id
    """
    return dict((await db.execute(text(sql), {"id": job_id})).mappings().one())


async def set_attempt_count(db: AsyncSession, job_id: uuid.UUID, value_sql: str) -> None:
    """Đặt attempt_count bằng biểu thức SQL cố định của test (vd `max_attempts`, `0`)."""
    await db.execute(
        text(f"UPDATE ai.video_analysis_jobs SET attempt_count = {value_sql} WHERE id = :id"), {"id": job_id}
    )
    await db.commit()


# --- SRT-07 ---
@pytest.mark.tc("SRT-07")
async def test_list_jobs_status_and_set_filters_return_matching_jobs(
    client: AsyncClient, auth_headers, db: AsyncSession
):
    headers, sets, (job_a, job_b, job_c) = await _demo_jobs(client, auth_headers, db, (0, 1, 0))
    s1, s2 = sets[0]["set_id"], sets[1]["set_id"]
    await video_job_service.record_failure(db, uuid.UUID(job_c["id"]), VideoJobFailureRequest(error_message="x"))
    cases: list[tuple[dict[str, Any], set[str]]] = [
        ({"set_id": s1}, {job_a["id"], job_c["id"]}),
        ({"status": "queued"}, {job_a["id"], job_b["id"]}),
        ({"status": "failed"}, {job_c["id"]}),
        ({"status": "failed", "set_id": s2}, set()),
        ({"set_id": await power_set(db)}, set()),
        ({"status": "completed"}, set()),
    ]
    for params, expected in cases:
        body = assert_page(await get_jobs(client, headers, params))
        assert _ids(body["data"]) == expected, params

    (failed,) = assert_page(await get_jobs(client, headers, {"status": "failed"}))["data"]
    assert failed["status"] == "failed"
    assert failed["finished_at"] is not None
    state = await job_state(db, uuid.UUID(job_c["id"]))
    assert (state["status"], state["error_message"]) == ("failed", "x")
    assert state["started_at"] is not None and state["finished_at"] >= state["started_at"]


# --- SRT-14 ---
@pytest.mark.tc("SRT-14")
async def test_start_job_queued_job_marks_processing(client: AsyncClient, auth_headers, db: AsyncSession):
    headers, _, (job,) = await _demo_jobs(client, auth_headers, db, (0,))
    job_id = uuid.UUID(job["id"])

    await video_job_service.start_job(db, job_id, "worker-01")

    state = await job_state(db, job_id)
    assert state["status"] == "processing"
    assert state["started_at"] is not None and state["started_at"] >= state["queued_at"]
    assert (state["attempt_count"], state["worker_id"]) == (1, "worker-01")
    listed = {item["id"]: item for item in assert_page(await get_jobs(client, headers))["data"]}
    item = listed[job["id"]]
    assert item["status"] == "processing"
    assert item["started_at"] is not None
    assert item["finished_at"] is None and item["analyzed_at"] is None


# --- SRT-15 ---
@pytest.mark.tc("SRT-15")
async def test_start_job_missing_or_exhausted_job_raises_not_found_or_conflict(
    client: AsyncClient, auth_headers, db: AsyncSession
):
    _, _, (job,) = await _demo_jobs(client, auth_headers, db, (0,))
    job_id = uuid.UUID(job["id"])

    with pytest.raises(NotFoundError) as missing:
        await video_job_service.start_job(db, uuid.uuid4(), "w")
    assert (missing.value.status_code, missing.value.code) == (404, "not_found")

    await set_attempt_count(db, job_id, "max_attempts")
    with pytest.raises(ConflictError) as exhausted:
        await video_job_service.start_job(db, job_id, "w")
    assert (exhausted.value.status_code, exhausted.value.code) == (409, "conflict")
    state = await job_state(db, job_id)
    assert state["status"] == "queued"
    assert state["attempt_count"] == state["max_attempts"]
    assert state["started_at"] is None and state["worker_id"] is None
    await set_attempt_count(db, job_id, "0")


@pytest.mark.tc("SRT-15")
async def test_start_job_invalid_worker_id_raises_validation_error(
    client: AsyncClient, auth_headers, db: AsyncSession
):
    _, _, (job,) = await _demo_jobs(client, auth_headers, db, (0,))
    job_id = uuid.UUID(job["id"])

    for worker_id in ("", "w" * 101):
        with pytest.raises(DataValidationError) as invalid:
            await video_job_service.start_job(db, job_id, worker_id)
        assert (invalid.value.status_code, invalid.value.code) == (422, "validation_error")
        assert invalid.value.details[0].field == "worker_id"

    state = await job_state(db, job_id)
    assert (state["status"], state["attempt_count"], state["worker_id"]) == ("queued", 0, None)
    assert state["started_at"] is None


@pytest.mark.tc("SRT-15")
async def test_start_job_already_started_raises_conflict(client: AsyncClient, auth_headers, db: AsyncSession):
    _, _, (job,) = await _demo_jobs(client, auth_headers, db, (0,))
    job_id = uuid.UUID(job["id"])
    await video_job_service.start_job(db, job_id, "w")

    with pytest.raises(ConflictError) as again:
        await video_job_service.start_job(db, job_id, "w")

    assert (again.value.status_code, again.value.code) == (409, "conflict")
    state = await job_state(db, job_id)
    assert (state["status"], state["attempt_count"]) == ("processing", 1)
