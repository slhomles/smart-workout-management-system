"""Integration test route worker video /ai/video-jobs/... (06-ai-contracts §3) trên PostgreSQL thật.

Fixture và helper theo "Quy ước chung" của spec be-video-worker-api §5. Helper dùng chung với module
set-rep-tempo được import đích danh từ test_video_jobs_api.py (không import hàm test_*).
Dữ liệu chuẩn bị được `db.commit()` (chỉ release savepoint), cuối test fixture `db` vẫn rollback.
"""

import hmac
import logging
import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from tests.integration.test_video_jobs_api import (
    assert_error,
    job_state,
    make_video,
    persona_user_id,
    post_job,
    set_attempt_count,
    squat_exercise,
    squat_sets,
)

BASE = "/api/v1/ai/video-jobs"
WT = "wt-test-" + "a" * 40
WH = {"X-Worker-Token": WT}
KEYS_CLAIM = {"job_id", "set_id", "exercise_id", "exercise_slug", "attempt_count", "source_video_content_type"}


# --- Fixture ---
@pytest.fixture
def worker_token(monkeypatch: pytest.MonkeyPatch) -> str:
    """Token worker giả của test (06 §4: không dùng giá trị thật)."""
    monkeypatch.setattr(get_settings(), "AI_WORKER_TOKEN", WT)
    return WT


@pytest.fixture
def local_storage(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Kho file local trong tmp_path (tiền lệ test_body_api.py)."""
    monkeypatch.setattr(get_settings(), "STORAGE_BACKEND", "local")
    monkeypatch.setattr(get_settings(), "LOCAL_STORAGE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
async def queue_clear(db: AsyncSession) -> None:
    """Huỷ job queued có sẵn trên DB dùng chung để không chen vào thứ tự claim (rollback cuối test)."""
    await db.execute(text("UPDATE ai.video_analysis_jobs SET status = 'cancelled' WHERE status = 'queued'"))
    await db.commit()


# --- Helper ---
async def claim(client: AsyncClient, worker_id: Any = "worker-01", headers: dict[str, str] | None = None) -> Response:
    """CLAIM(w) của spec §5; mặc định gửi WH."""
    return await client.post(f"{BASE}/claim", json={"worker_id": worker_id}, headers=WH if headers is None else headers)


async def create_jobs(client: AsyncClient, auth_headers, db: AsyncSession, set_keys: tuple[int, ...]) -> list[str]:
    """JOB(S<k>) cho từng k (0 = S1, 1 = S2) với V_DEMO; trả id các job (chuỗi UUID)."""
    sets = await squat_sets(db)
    v_demo = await make_video(db, await persona_user_id(db, "demo"))
    headers = await auth_headers("demo")
    ids = []
    for key in set_keys:
        res = await post_job(client, headers, sets[key]["set_id"], v_demo)
        assert res.status_code == 202, res.text
        ids.append(res.json()["id"])
    return ids


async def set_queue_position(db: AsyncSession, job_id: str, priority: int, minutes_ago: int) -> None:
    """Đặt priority và queued_at = now() - minutes_ago phút cho job."""
    sql = """
    UPDATE ai.video_analysis_jobs
    SET priority = :priority, queued_at = now() - make_interval(mins => :minutes)
    WHERE id = :id
    """
    await db.execute(text(sql), {"priority": priority, "minutes": minutes_ago, "id": job_id})
    await db.commit()


async def soft_delete_session(db: AsyncSession, session_id: uuid.UUID) -> None:
    """Xoá mềm SESS(Sx)."""
    await db.execute(text("UPDATE training.workout_sessions SET deleted_at = now() WHERE id = :id"), {"id": session_id})
    await db.commit()


async def count_jobs(db: AsyncSession) -> int:
    """Số dòng ai.video_analysis_jobs."""
    return int(await db.scalar(text("SELECT count(*) FROM ai.video_analysis_jobs")))


def assert_claimed(res: Response) -> dict[str, Any]:
    """200 + body đúng KEYS-CLAIM, không envelope; trả body."""
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == KEYS_CLAIM
    return body


def assert_no_content(res: Response) -> None:
    """204 không body."""
    assert res.status_code == 204, res.text
    assert res.content == b""


# --- VWK-01 ---
@pytest.mark.tc("VWK-01")
@pytest.mark.usefixtures("worker_token", "queue_clear")
async def test_claim_queued_jobs_returns_highest_priority_then_oldest_then_no_content(
    client: AsyncClient, auth_headers, db: AsyncSession
):
    job_a, job_b, job_c = await create_jobs(client, auth_headers, db, (0, 1, 0))
    await set_queue_position(db, job_a, priority=5, minutes_ago=10)
    await set_queue_position(db, job_b, priority=5, minutes_ago=20)
    await set_queue_position(db, job_c, priority=8, minutes_ago=1)

    bodies = [assert_claimed(await claim(client)) for _ in range(3)]
    assert_no_content(await claim(client))

    assert [body["job_id"] for body in bodies] == [job_c, job_b, job_a]
    await _assert_claim_body_of_c(db, bodies[0])
    for job_id in (job_a, job_b, job_c):
        state = await job_state(db, uuid.UUID(job_id))
        assert (state["status"], state["worker_id"], state["attempt_count"]) == ("processing", "worker-01", 1)
        assert state["started_at"] is not None


async def _assert_claim_body_of_c(db: AsyncSession, body: dict[str, Any]) -> None:
    s1 = (await squat_sets(db))[0]["set_id"]
    squat_id, _ = await squat_exercise(db)
    assert isinstance(body["job_id"], str) and str(uuid.UUID(body["job_id"])) == body["job_id"]
    assert type(body["set_id"]) is int and body["set_id"] == s1
    assert type(body["exercise_id"]) is int and body["exercise_id"] == squat_id
    assert body["exercise_slug"] == "barbell-back-squat"
    assert body["attempt_count"] == 1
    assert body["source_video_content_type"] == "video/mp4"


# --- VWK-02 ---
@pytest.mark.tc("VWK-02")
@pytest.mark.usefixtures("worker_token", "queue_clear")
async def test_claim_exhausted_or_deleted_session_jobs_returns_no_content(
    client: AsyncClient, auth_headers, db: AsyncSession
):
    job_d, job_e = await create_jobs(client, auth_headers, db, (0, 1))
    await set_attempt_count(db, uuid.UUID(job_d), "max_attempts")
    await soft_delete_session(db, (await squat_sets(db))[1]["session_id"])

    assert_no_content(await claim(client))

    state_d = await job_state(db, uuid.UUID(job_d))
    assert (state_d["status"], state_d["attempt_count"], state_d["worker_id"]) == ("queued", 3, None)
    state_e = await job_state(db, uuid.UUID(job_e))
    assert (state_e["status"], state_e["attempt_count"], state_e["started_at"]) == ("queued", 0, None)


# --- VWK-03 ---
@pytest.mark.tc("VWK-03")
@pytest.mark.usefixtures("worker_token", "queue_clear")
async def test_claim_invalid_worker_id_returns_validation_error(
    client: AsyncClient, auth_headers, db: AsyncSession
):
    (job_j,) = await create_jobs(client, auth_headers, db, (0,))
    bodies: list[dict[str, Any]] = [{}, {"worker_id": ""}, {"worker_id": "w" * 101}, {"worker_id": 123}]

    for body in bodies:
        res = await client.post(f"{BASE}/claim", json=body, headers=WH)
        error = assert_error(res, 422, "validation_error")
        assert any("worker_id" in (detail["field"] or "") for detail in error["details"]), (body, error)

    state = await job_state(db, uuid.UUID(job_j))
    assert (state["status"], state["attempt_count"], state["worker_id"]) == ("queued", 0, None)


# --- VWK-05 ---
@pytest.mark.tc("VWK-05")
@pytest.mark.usefixtures("worker_token", "queue_clear")
async def test_user_routes_with_worker_token_only_returns_token_invalid(
    client: AsyncClient, auth_headers, db: AsyncSession
):
    (job_j,) = await create_jobs(client, auth_headers, db, (0,))
    s1 = (await squat_sets(db))[0]["set_id"]
    v_demo = await db.scalar(
        text("SELECT source_video_media_id FROM ai.video_analysis_jobs WHERE id = :id"), {"id": job_j}
    )
    before = await count_jobs(db)

    assert_error(await client.get(BASE, headers=WH), 401, "token_invalid")
    assert_error(await post_job(client, WH, s1, v_demo), 401, "token_invalid")

    assert await count_jobs(db) == before
    res = await client.get(BASE, headers=await auth_headers("demo"))
    assert res.status_code == 200, res.text
    assert job_j in {item["id"] for item in res.json()["data"]}


# --- VWK-16 ---
@pytest.mark.tc("VWK-16")
@pytest.mark.usefixtures("worker_token", "queue_clear")
async def test_claim_compares_token_with_compare_digest_and_never_logs_it(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
):
    caplog.set_level(logging.DEBUG)
    calls: list[tuple[Any, ...]] = []
    original = hmac.compare_digest

    def _spy(*args: Any) -> bool:
        calls.append(args)
        return original(*args)

    monkeypatch.setattr(hmac, "compare_digest", _spy)
    wrong_token = "sai-" + "b" * 40

    assert_no_content(await claim(client))
    assert_error(await claim(client, headers={"X-Worker-Token": wrong_token}), 401, "unauthorized")

    assert len(calls) >= 2
    assert all(len(args) == 2 and all(isinstance(arg, bytes) for arg in args) for args in calls)
    assert WT not in caplog.text
    assert wrong_token not in caplog.text
