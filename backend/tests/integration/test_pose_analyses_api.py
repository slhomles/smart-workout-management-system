"""Integration test /ai/pose-analyses (chức năng 5: chỉnh tư thế) trên PostgreSQL thật.

Mọi id seed đọc qua `db` (fixture `seed`), không hard-code; quy ước tên theo spec posture-correction §5.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

BASE = "/api/v1/ai/pose-analyses"
KEYS_PA = {
    "id", "set_id", "session_id", "exercise_id", "exercise_name", "mode", "model_name", "model_version",
    "overall_score", "correct_form_pct", "detected_rep_count", "feedback_summary", "keypoints_media_id",
    "video_job_status", "result_video_media_id", "issue_count", "critical_issue_count", "analyzed_at",
    "created_at", "issues",
}
KEYS_ISSUE = {"id", "mistake_id", "rep_no", "offset_ms", "frame_index", "severity", "measured_angle_deg"}
UUID_KEYS = ("id", "session_id", "keypoints_media_id", "result_video_media_id")
INT_KEYS = ("set_id", "exercise_id", "issue_count", "critical_issue_count")
NUMBER_KEYS = ("overall_score", "correct_form_pct")
TIME_KEYS = ("analyzed_at", "created_at")
MISSING = object()

_SEED_SQL = """
WITH sets AS (
    SELECT es.id, es.set_no, s.id AS session_id, s.started_at, s.deleted_at, s.name AS session_name,
           u.email, e.slug, e.supports_ai_tracking
    FROM training.exercise_sets es
    JOIN training.session_exercises se ON se.id = es.session_exercise_id
    JOIN training.workout_sessions s ON s.id = se.session_id
    JOIN auth.users u ON u.id = s.user_id
    JOIN catalog.exercises e ON e.id = se.exercise_id
),
squat AS (
    SELECT DISTINCT ON (started_at, session_id) id, session_id, started_at
    FROM sets
    WHERE email = 'demo@smartworkout.local' AND slug = 'barbell-back-squat' AND set_no = 1 AND deleted_at IS NULL
    ORDER BY started_at DESC, session_id, id
    LIMIT 3
)
SELECT
    (SELECT array_agg(id ORDER BY started_at DESC) FROM squat) AS squat_sets,
    (SELECT array_agg(session_id ORDER BY started_at DESC) FROM squat) AS squat_sessions,
    (SELECT min(id) FROM sets WHERE email = 'demo@smartworkout.local' AND slug = 'barbell-bench-press'
        AND deleted_at IS NULL) AS bench,
    (SELECT min(id) FROM sets WHERE email = 'demo@smartworkout.local' AND slug = 'hammer-curl'
        AND deleted_at IS NULL) AS hammer,
    (SELECT min(id) FROM sets WHERE email = 'power@smartworkout.local' AND supports_ai_tracking
        AND deleted_at IS NULL) AS power_set,
    (SELECT min(id) FROM sets WHERE email = 'inprogress@smartworkout.local' AND slug = 'push-up'
        AND session_name = 'Buổi nhập nhầm' AND deleted_at IS NOT NULL) AS deleted_set,
    (SELECT min(id) FROM sets WHERE email = 'trainer@smartworkout.local' AND slug = 'barbell-back-squat'
        AND deleted_at IS NULL) AS trainer_set,
    (SELECT max(id) FROM training.exercise_sets) + 1000 AS missing_set,
    (SELECT id FROM catalog.exercises WHERE slug = 'barbell-back-squat') AS squat_id,
    (SELECT name FROM catalog.exercises WHERE slug = 'barbell-back-squat') AS squat_name,
    (SELECT id FROM catalog.exercises WHERE slug = 'barbell-bench-press') AS bench_id,
    (SELECT id FROM catalog.exercise_mistakes WHERE code = 'SQUAT_BACK_ROUNDING') AS m_back,
    (SELECT id FROM catalog.exercise_mistakes WHERE code = 'SQUAT_KNEE_VALGUS') AS m_valgus,
    (SELECT id FROM catalog.exercise_mistakes WHERE code = 'SQUAT_HEEL_LIFT') AS m_heel,
    (SELECT id FROM catalog.exercise_mistakes WHERE code = 'BENCH_ELBOW_FLARE') AS m_bench,
    now() AS now
"""


# --- Dữ liệu seed & tiện ích ---
@pytest.fixture
async def seed(db: AsyncSession) -> dict[str, Any]:
    """Id seed theo tên trong spec §5 (S1..S3, SESS1..SESS3, BENCH, HAMMER, ..., NOW), một truy vấn."""
    row = dict((await db.execute(text(_SEED_SQL))).mappings().one())
    sets, sessions = row.pop("squat_sets"), row.pop("squat_sessions")
    values = {key.upper(): value for key, value in row.items()}
    values.update({f"S{n}": sets[n - 1] for n in (1, 2, 3)})
    values.update({f"SESS{n}": str(sessions[n - 1]) for n in (1, 2, 3)})
    assert None not in values.values() and len(set(sessions)) == 3, values
    return values


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _v(set_id: int, **extra: Any) -> dict[str, Any]:
    """Body hợp lệ tối thiểu V(set) của spec §5."""
    body = {"set_id": set_id, "model_name": "mediapipe_blazepose", "model_version": "0.10.14", "correct_form_pct": 100}
    return {**body, **extra}


def _pose01_body(seed: dict[str, Any]) -> dict[str, Any]:
    return _v(
        seed["S1"],
        overall_score=82.5,
        correct_form_pct=76.0,
        detected_rep_count=8,
        feedback_summary="Lưng dưới bị cong ở rep 3",
        analyzed_at=_iso(seed["NOW"] - timedelta(minutes=10)),
        issues=[
            {"mistake_id": seed["M_VALGUS"], "rep_no": 5, "offset_ms": 21000, "frame_index": None,
             "severity": "warning", "measured_angle_deg": 165.0},
            {"mistake_id": seed["M_BACK"], "rep_no": 3, "offset_ms": 12500, "severity": "critical",
             "measured_angle_deg": 142.5},
        ],
    )


def _is_uuid(value: Any) -> bool:
    try:
        uuid.UUID(value)
    except (TypeError, ValueError, AttributeError):
        return False
    return True


def _top_shape(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "keys": set(body),
        "uuid": all(body[k] is None or _is_uuid(body[k]) for k in UUID_KEYS),
        "int": all(type(body[k]) is int for k in INT_KEYS),
        "number": all(body[k] is None or type(body[k]) in (int, float) for k in NUMBER_KEYS),
        "utc": all(body[k] is None or body[k].endswith("Z") for k in TIME_KEYS),
    }


def _issue_shape(issue: dict[str, Any]) -> dict[str, Any]:
    angle = issue["measured_angle_deg"]
    return {
        "keys": set(issue),
        "int": type(issue["id"]) is int and type(issue["mistake_id"]) is int,
        "number": angle is None or type(angle) in (int, float),
    }


def _assert_shape(body: dict[str, Any]) -> None:
    """Đúng KEYS-PA / KEYS-ISSUE và kiểu JSON của spec §5."""
    assert _top_shape(body) == {"keys": KEYS_PA, "uuid": True, "int": True, "number": True, "utc": True}
    expected_issue = {"keys": KEYS_ISSUE, "int": True, "number": True}
    assert [_issue_shape(i) for i in body["issues"]] == [expected_issue] * len(body["issues"])


def _created(res: Response) -> dict[str, Any]:
    assert res.status_code == 201, res.text
    body = res.json()
    assert res.headers["Location"] == f"{BASE}/{body['id']}"
    _assert_shape(body)
    return body


def _error(res: Response, status: int, code: str) -> dict[str, Any]:
    assert res.status_code == status, res.text
    body = res.json()
    assert set(body) == {"error"} and set(body["error"]) == {"code", "message", "details", "request_id"}
    assert body["error"]["code"] == code and isinstance(body["error"]["details"], list)
    return body["error"]


def _fields(error: dict[str, Any]) -> list[str | None]:
    return [d["field"] for d in error["details"]]


def _pick(body: dict[str, Any], keys: Any) -> dict[str, Any]:
    return {k: body[k] for k in keys}


def _without_id(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in issue.items() if k != "id"} for issue in issues]


async def _ai_counts(db: AsyncSession) -> tuple[int, int]:
    sql = "SELECT (SELECT count(*) FROM ai.pose_analyses), (SELECT count(*) FROM ai.posture_issues)"
    row = (await db.execute(text(sql))).one()
    return row[0], row[1]


@dataclass
class Api:
    """Gom fixture của conftest (client, db, auth_headers) và id seed để test gọn tham số."""

    client: AsyncClient
    db: AsyncSession
    seed: dict[str, Any]
    auth_headers: Callable[[str], Awaitable[dict[str, str]]]

    async def post(self, persona: str, body: dict[str, Any]) -> Response:
        return await self.client.post(BASE, json=body, headers=await self.auth_headers(persona))


@pytest.fixture
async def api(client: AsyncClient, db: AsyncSession, seed: dict[str, Any], auth_headers) -> Api:
    return Api(client, db, seed, auth_headers)


# --- POSE-01: tạo đủ trường ---
@pytest.mark.tc("POSE-01")
async def test_create_analysis_full_body_returns_201_and_persists(api: Api):
    seed, db = api.seed, api.db
    set_sql = text("SELECT source, reps, updated_at FROM training.exercise_sets WHERE id = :id")
    set_before = (await db.execute(set_sql, {"id": seed["S1"]})).one()
    sent = _pose01_body(seed)
    body = _created(await api.post("demo", sent))

    assert _pick(body, ("set_id", "session_id", "exercise_id", "exercise_name", "mode", "model_name",
                        "model_version", "feedback_summary", "overall_score", "correct_form_pct",
                        "detected_rep_count", "keypoints_media_id", "video_job_status", "result_video_media_id",
                        "issue_count", "critical_issue_count")) == {
        "set_id": seed["S1"], "session_id": seed["SESS1"], "exercise_id": seed["SQUAT_ID"],
        "exercise_name": seed["SQUAT_NAME"], "mode": "realtime_edge", "model_name": "mediapipe_blazepose",
        "model_version": "0.10.14", "feedback_summary": "Lưng dưới bị cong ở rep 3", "overall_score": 82.5,
        "correct_form_pct": 76.0, "detected_rep_count": 8, "keypoints_media_id": None, "video_job_status": None,
        "result_video_media_id": None, "issue_count": 2, "critical_issue_count": 1,
    }
    assert datetime.fromisoformat(body["analyzed_at"]) == datetime.fromisoformat(sent["analyzed_at"])
    assert _without_id(body["issues"]) == [
        {"mistake_id": seed["M_BACK"], "rep_no": 3, "offset_ms": 12500, "frame_index": None,
         "severity": "critical", "measured_angle_deg": 142.5},
        {"mistake_id": seed["M_VALGUS"], "rep_no": 5, "offset_ms": 21000, "frame_index": None,
         "severity": "warning", "measured_angle_deg": 165.0},
    ]
    assert body["issues"][0]["id"] != body["issues"][1]["id"]

    stored = (await db.execute(text(
        "SELECT (SELECT count(*) FROM ai.pose_analyses WHERE id = :id AND set_id = :set_id"
        "        AND mode = 'realtime_edge' AND analyzed_at IS NOT NULL),"
        "       (SELECT count(*) FROM ai.posture_issues WHERE pose_analysis_id = :id)"
    ), {"id": body["id"], "set_id": seed["S1"]})).one()
    assert tuple(stored) == (1, 2)
    assert (await db.execute(set_sql, {"id": seed["S1"]})).one() == set_before


# --- POSE-02: mặc định, biên, gửi lặp ---
@pytest.mark.tc("POSE-02")
async def test_create_analysis_minimal_body_uses_defaults_and_allows_repeat(api: Api):
    seed = api.seed
    first = _created(await api.post("demo", _v(seed["S2"])))
    assert _pick(first, ("overall_score", "detected_rep_count", "feedback_summary", "correct_form_pct",
                         "issues", "issue_count", "critical_issue_count")) == {
        "overall_score": None, "detected_rep_count": None, "feedback_summary": None, "correct_form_pct": 100.0,
        "issues": [], "issue_count": 0, "critical_issue_count": 0,
    }
    assert abs(datetime.fromisoformat(first["analyzed_at"]) - seed["NOW"]) <= timedelta(seconds=60)

    second = _created(await api.post("demo", _v(seed["S2"])))
    assert second["id"] != first["id"]
    count_sql = text("SELECT count(*) FROM ai.pose_analyses WHERE set_id = :set_id")
    assert await api.db.scalar(count_sql, {"set_id": seed["S2"]}) == 2


@pytest.mark.tc("POSE-02")
async def test_create_analysis_issue_without_optionals_defaults_to_warning(api: Api):
    seed = api.seed
    sent = _v(seed["S3"], issues=[{"mistake_id": seed["M_HEEL"], "offset_ms": 0}])
    body = _created(await api.post("demo", sent))
    assert _without_id(body["issues"]) == [
        {"mistake_id": seed["M_HEEL"], "rep_no": None, "offset_ms": 0, "frame_index": None,
         "severity": "warning", "measured_angle_deg": None},
    ]


@pytest.mark.tc("POSE-02")
async def test_create_analysis_boundary_values_returns_201(api: Api):
    seed = api.seed
    issue = {"mistake_id": seed["M_BACK"], "offset_ms": 1, "rep_no": 1, "frame_index": 0, "measured_angle_deg": 360}
    sent = _v(seed["S1"], correct_form_pct=0, overall_score=100, detected_rep_count=0,
              analyzed_at=_iso(seed["NOW"] + timedelta(minutes=4)), issues=[issue])
    body = _created(await api.post("demo", sent))
    assert _pick(body, ("correct_form_pct", "overall_score", "detected_rep_count")) == {
        "correct_form_pct": 0.0, "overall_score": 100.0, "detected_rep_count": 0,
    }
    assert _pick(body["issues"][0], ("measured_angle_deg", "frame_index")) == {"measured_angle_deg": 360.0, "frame_index": 0}


# --- POSE-03: lỗi validation đầu vào ---
def _edit(body: dict[str, Any], path: str, value: Any) -> None:
    """Đổi đúng một chỗ trong body theo đường dẫn `a.0.b`; MISSING = xoá key."""
    *parents, last = path.split(".")
    target: Any = body
    for key in parents:
        target = target[int(key)] if key.isdigit() else target[key]
    if value is MISSING:
        del target[last]
    else:
        target[last] = value


def _valid_issue(seed: dict[str, Any]) -> dict[str, Any]:
    return {"mistake_id": seed["M_BACK"], "offset_ms": 100}


# (đường dẫn cần đổi, giá trị mới | MISSING | hàm(seed), field phải có trong details)
INVALID_INPUTS: list[tuple[str, Any, str]] = [
    ("set_id", MISSING, "set_id"),
    ("set_id", "abc", "set_id"),
    ("set_id", 0, "set_id"),
    ("set_id", 9223372036854775808, "set_id"),
    ("model_name", MISSING, "model_name"),
    ("model_name", "", "model_name"),
    ("model_version", "v" * 51, "model_version"),
    ("correct_form_pct", MISSING, "correct_form_pct"),
    ("correct_form_pct", 100.01, "correct_form_pct"),
    ("overall_score", -0.5, "overall_score"),
    ("detected_rep_count", -1, "detected_rep_count"),
    ("feedback_summary", "x" * 2001, "feedback_summary"),
    ("analyzed_at", "2026-01-01T00:00:00", "analyzed_at"),
    ("analyzed_at", lambda s: _iso(s["NOW"] + timedelta(days=1)), "analyzed_at"),
    ("issues.0.offset_ms", -1, "issues.0.offset_ms"),
    ("issues.0.rep_no", 0, "issues.0.rep_no"),
    ("issues.0.frame_index", -1, "issues.0.frame_index"),
    ("issues.0.severity", "fatal", "issues.0.severity"),
    ("issues.0.measured_angle_deg", 360.01, "issues.0.measured_angle_deg"),
    ("issues.0.mistake_id", MISSING, "issues.0.mistake_id"),
    ("issues", lambda s: [_valid_issue(s) for _ in range(501)], "issues"),
]


@pytest.mark.tc("POSE-03")
@pytest.mark.parametrize("case", INVALID_INPUTS, ids=[f"{n + 1}-{c[0]}" for n, c in enumerate(INVALID_INPUTS)])
async def test_create_analysis_invalid_input_returns_422(api: Api, case: tuple[str, Any, str]):
    path, value, field = case
    counts_before = await _ai_counts(api.db)
    sent = _v(api.seed["S1"], issues=[_valid_issue(api.seed)])
    _edit(sent, path, value(api.seed) if callable(value) else value)
    error = _error(await api.post("demo", sent), 422, "validation_error")
    assert field in _fields(error), error
    assert await _ai_counts(api.db) == counts_before


# --- POSE-04: lỗi nghiệp vụ ---
# (khoá hiệp trong seed, [(khoá mã lỗi trong seed hoặc id thô, offset_ms)], field phải có trong details)
BUSINESS_ERRORS: list[tuple[str, list[tuple[str | int, int]], str]] = [
    ("HAMMER", [], "set_id"),
    ("S1", [("M_BACK", 100), ("M_BENCH", 200)], "issues.1.mistake_id"),
    ("S1", [(2147483647, 100)], "issues.0.mistake_id"),
    ("BENCH", [("M_BACK", 0)], "issues.0.mistake_id"),
]


@pytest.mark.tc("POSE-04")
@pytest.mark.parametrize("case", BUSINESS_ERRORS, ids=["hammer", "other-exercise", "unknown", "bench"])
async def test_create_analysis_business_rule_violation_returns_422(
    api: Api, case: tuple[str, list[tuple[str | int, int]], str]
):
    set_key, issues, field = case
    counts_before = await _ai_counts(api.db)
    sent = _v(api.seed[set_key], issues=[
        {"mistake_id": api.seed.get(str(mistake), mistake), "offset_ms": offset} for mistake, offset in issues
    ])
    error = _error(await api.post("demo", sent), 422, "validation_error")
    assert field in _fields(error), error
    assert await _ai_counts(api.db) == counts_before


# --- POSE-05: hiệp không thuộc user / không tồn tại ---
async def _soft_delete_s1_session(api: Api) -> None:
    sql = text("UPDATE training.workout_sessions SET deleted_at = now() WHERE id = :id")
    await api.db.execute(sql, {"id": api.seed["SESS1"]})


async def _no_setup(api: Api) -> None:
    return None


# (persona gửi, khoá hiệp trong seed, bước chuẩn bị qua db)
NOT_OWNED_SETS: list[tuple[str, str, Callable[[Api], Awaitable[None]]]] = [
    ("demo", "POWER_SET", _no_setup),
    ("demo", "MISSING_SET", _no_setup),
    ("inprogress", "DELETED_SET", _no_setup),
    ("demo", "S1", _soft_delete_s1_session),
]


@pytest.mark.tc("POSE-05")
@pytest.mark.parametrize("case", NOT_OWNED_SETS, ids=["other-user", "missing", "deleted", "deleted-now"])
async def test_create_analysis_set_not_owned_returns_404(
    api: Api, case: tuple[str, str, Callable[[Api], Awaitable[None]]]
):
    persona, set_key, setup = case
    await setup(api)
    counts_before = await _ai_counts(api.db)
    error = _error(await api.post(persona, _v(api.seed[set_key])), 404, "exercise_set_not_found")
    assert error["details"] == []
    assert await _ai_counts(api.db) == counts_before


@pytest.mark.tc("POSE-05")
async def test_create_analysis_foreign_and_missing_set_share_message(api: Api):
    foreign = _error(await api.post("demo", _v(api.seed["POWER_SET"])), 404, "exercise_set_not_found")
    missing = _error(await api.post("demo", _v(api.seed["MISSING_SET"])), 404, "exercise_set_not_found")
    assert foreign["message"] == missing["message"]
