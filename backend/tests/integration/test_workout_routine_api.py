"""Integration test chức năng 2 (Workout Routine): /workout-plans, /scheduled-workouts, /recovery.

Chạy trên PostgreSQL thật, mỗi test trong transaction rollback (fixture `db` của conftest).
Test case theo spec docs/features/workout-routine.md §5 (mã WRT-xx).
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text

from app.core.config import get_settings
from app.schemas.base import encode_cursor
from app.schemas.recovery import RecoveryPredictionInput, RecoveryPredictionOutput
from app.services import recovery_ai_client

PLANS = "/api/v1/workout-plans"

KEYS_PLAN = {
    "id", "name", "description", "source_plan_id", "goal_type_id", "difficulty_level_id", "duration_weeks",
    "status", "days", "created_at", "updated_at",
}
KEYS_DAY = {"id", "day_no", "name", "notes", "exercises"}
KEYS_PEX = {
    "id", "order_no", "exercise", "target_sets", "target_reps_min", "target_reps_max", "target_duration_seconds",
    "target_weight_kg", "target_rpe", "rest_seconds", "tempo_eccentric_s", "tempo_pause_bottom_s",
    "tempo_concentric_s", "tempo_pause_top_s", "notes",
}
KEYS_EXERCISE_REF = {"id", "slug", "name", "supports_ai_tracking"}
KEYS_ERROR = {"code", "message", "details", "request_id"}
TARGET_KEYS = (
    "target_sets", "target_reps_min", "target_reps_max", "target_rpe", "rest_seconds", "tempo_eccentric_s",
    "tempo_pause_bottom_s", "tempo_concentric_s", "tempo_pause_top_s", "target_weight_kg",
    "target_duration_seconds",
)


def T(n: int) -> str:
    """UUID giáo án mẫu seed (T1…T8)."""
    return f"5eed1000-0000-4000-8000-{n:012d}"


def _keys(obj: dict, expected: set[str]) -> None:
    assert set(obj) == expected, sorted(set(obj) ^ expected)


def _pick(obj: dict, keys: tuple[str, ...]) -> dict:
    return {key: obj[key] for key in keys}


def _err(res: Response, status: int, code: str) -> dict:
    """Kiểm tra body lỗi chuẩn và trả `error`."""
    assert res.status_code == status, res.text
    body = res.json()
    _keys(body, {"error"})
    _keys(body["error"], KEYS_ERROR)
    assert body["error"]["code"] == code, body
    return body["error"]


def _fields(error: dict) -> list[str | None]:
    return [detail["field"] for detail in error["details"]]


def _ok_page(res: Response) -> dict:
    """Kiểm tra 200 + `Page[T]` (đúng 2 key `data`, `pagination`), trả body."""
    assert res.status_code == 200, res.text
    body = res.json()
    _keys(body, {"data", "pagination"})
    _keys(body["pagination"], {"next_cursor", "has_more"})
    return body


def _only_item(body: dict) -> dict:
    assert len(body["data"]) == 1, body["data"]
    return body["data"][0]


def _assert_plan_shape(plan: dict) -> None:
    """Đúng KEYS-PLAN/DAY/PEX, thời điểm hậu tố Z, `order_no` tăng dần từ 1 trong mỗi buổi."""
    _keys(plan, KEYS_PLAN)
    assert plan["created_at"].endswith("Z") and plan["updated_at"].endswith("Z"), plan
    for day in plan["days"]:
        _keys(day, KEYS_DAY)
        assert [pex["order_no"] for pex in day["exercises"]] == list(range(1, len(day["exercises"]) + 1))
        for pex in day["exercises"]:
            _keys(pex, KEYS_PEX)
            _keys(pex["exercise"], KEYS_EXERCISE_REF)


async def _list_plans(client: AsyncClient, headers: dict, **params: Any) -> dict:
    return _ok_page(await client.get(PLANS, params=params, headers=headers))


# --- GET /workout-plans ---
@pytest.mark.tc("WRT-01")
async def test_list_plans_demo_returns_cloned_ppl_with_days_and_exercises(client: AsyncClient, db, auth_headers):
    body = await _list_plans(client, await auth_headers("demo"))
    assert body["pagination"] == {"next_cursor": None, "has_more": False}
    plan = _only_item(body)
    _assert_plan_shape(plan)
    gain_muscle = await db.scalar(text("SELECT id FROM body.fitness_goal_types WHERE code = 'gain_muscle'"))
    assert _pick(plan, ("name", "status", "source_plan_id", "duration_weeks", "goal_type_id")) == {
        "name": "PPL của An", "status": "active", "source_plan_id": T(2), "duration_weeks": 12,
        "goal_type_id": gain_muscle,
    }
    assert [(day["day_no"], day["name"], len(day["exercises"])) for day in plan["days"]] == [
        (1, "Push – Ngực/Vai/Tay sau", 6), (2, "Pull – Lưng/Tay trước", 6), (3, "Legs – Chân/Mông", 5),
    ]
    first = plan["days"][0]["exercises"][0]
    assert first["exercise"]["slug"] == "barbell-bench-press"
    assert _pick(first, TARGET_KEYS) == {
        "target_sets": 4, "target_reps_min": 6, "target_reps_max": 8, "target_rpe": 8.0, "rest_seconds": 150,
        "tempo_eccentric_s": 3, "tempo_pause_bottom_s": 1, "tempo_concentric_s": 1, "tempo_pause_top_s": 0,
        "target_weight_kg": None, "target_duration_seconds": None,
    }


async def _check_plateau_default_list(client: AsyncClient, headers: dict) -> None:
    """(a) Giáo án tự tạo trước, giáo án archived sau; không có nháp đã xoá mềm và giáo án mẫu."""
    plans = (await _list_plans(client, headers))["data"]
    assert [plan["name"] for plan in plans] == ["Giáo án tự tạo của Hải", "Full Body (cũ)"]
    assert not {plan["id"] for plan in plans} & {T(n) for n in range(1, 9)}
    own = plans[0]
    _assert_plan_shape(own)
    assert (own["source_plan_id"], len(own["days"])) == (None, 2)
    cardio = own["days"][1]["exercises"][2]
    assert (cardio["exercise"]["slug"], cardio["target_duration_seconds"], cardio["target_reps_min"]) == (
        "incline-treadmill-walk", 1200, None,
    )


async def _check_plateau_pagination(client: AsyncClient, headers: dict) -> None:
    """(b) limit=1, lần theo next_cursor tới trang cuối."""
    first = await _list_plans(client, headers, limit=1)
    assert (len(first["data"]), first["pagination"]["has_more"]) == (1, True)
    second = await _list_plans(client, headers, limit=1, cursor=first["pagination"]["next_cursor"])
    assert second["pagination"] == {"next_cursor": None, "has_more": False}
    assert len({first["data"][0]["id"], _only_item(second)["id"]}) == 2


@pytest.mark.tc("WRT-02")
async def test_list_plans_filter_paginate_and_skip_soft_deleted(client: AsyncClient, auth_headers):
    plateau = await auth_headers("plateau")
    await _check_plateau_default_list(client, plateau)
    await _check_plateau_pagination(client, plateau)
    archived = _only_item(await _list_plans(client, plateau, status="archived"))
    assert (archived["name"], archived["status"]) == ("Full Body (cũ)", "archived")
    draft = _only_item(await _list_plans(client, await auth_headers("trainer"), status="draft"))
    assert draft["name"] == "Giáo án cho khách mới (nháp)"


@pytest.mark.tc("WRT-03")
async def test_list_plans_invalid_query_returns_422_and_no_plan_returns_empty(client: AsyncClient, auth_headers):
    demo = await auth_headers("demo")
    cases = [
        ({"limit": 0}, "limit"),
        ({"limit": 101}, "limit"),
        ({"cursor": "!!!khong-phai-cursor"}, "cursor"),
        ({"cursor": encode_cursor({"foo": 1})}, "cursor"),
        ({"status": "deleted"}, "status"),
    ]
    fields = [
        _fields(_err(await client.get(PLANS, params=params, headers=demo), 422, "validation_error"))
        for params, _ in cases
    ]
    assert fields == [[field] for _, field in cases]
    empty = {"data": [], "pagination": {"next_cursor": None, "has_more": False}}
    assert [await _list_plans(client, await auth_headers(p)) for p in ("newbie", "dung")] == [empty, empty]


async def test_list_plans_without_token_or_permission_is_rejected(client: AsyncClient, auth_headers):
    res = await client.get(PLANS)
    _err(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"
    _err(await client.get(PLANS, headers=await auth_headers("editor")), 403, "permission_denied")


# --- POST /workout-plans ---
PLAN_COLUMNS = ("name", "description", "goal_type_id", "difficulty_level_id", "duration_weeks")
PEX_COLUMNS = (
    "exercise_id", "target_sets", "target_reps_min", "target_reps_max", "target_duration_seconds",
    "target_weight_kg", "target_rpe", "rest_seconds", "tempo_eccentric_s", "tempo_pause_bottom_s",
    "tempo_concentric_s", "tempo_pause_top_s",
)
TEMPO_KEYS = ("tempo_eccentric_s", "tempo_pause_bottom_s", "tempo_concentric_s", "tempo_pause_top_s")
NEWBIE_ID = "5eed0000-0000-4000-8000-000000000008"
DEMO_ID = "5eed0000-0000-4000-8000-000000000003"
SLUGS = (
    "barbell-bench-press", "lat-pulldown", "incline-treadmill-walk", "test-draft-exercise", "test-deleted-exercise",
)


async def _refs(db) -> dict[str, int]:
    """ID bài tập theo slug, `lose_fat` và `beginner`, đọc trong một truy vấn."""
    rows = await db.execute(
        text(
            "SELECT slug AS key, id FROM catalog.exercises WHERE slug = ANY(:slugs)"
            " UNION ALL SELECT code, id FROM body.fitness_goal_types WHERE code = 'lose_fat'"
            " UNION ALL SELECT code, id FROM catalog.difficulty_levels WHERE code = 'beginner'"
        ),
        {"slugs": list(SLUGS)},
    )
    refs = {row.key: row.id for row in rows}
    assert len(refs) == len(SLUGS) + 2, refs
    return refs


def _plan_body(refs: dict[str, int]) -> dict:
    """PLAN-BODY của spec WRT-05 (mỗi lần gọi trả bản mới để từng ca sửa riêng)."""
    bench = {
        "exercise_id": refs["barbell-bench-press"], "target_sets": 4, "target_reps_min": 6, "target_reps_max": 8,
        "target_weight_kg": 60, "target_rpe": 8, "rest_seconds": 150, "tempo_eccentric_s": 3,
        "tempo_pause_bottom_s": 1, "tempo_concentric_s": 1, "tempo_pause_top_s": 0,
    }
    pulldown = {"exercise_id": refs["lat-pulldown"], "target_sets": 3, "target_reps_min": 10, "target_reps_max": 12}
    walk = {"exercise_id": refs["incline-treadmill-walk"], "target_sets": 1, "target_duration_seconds": 1200}
    return {
        "name": "  Giáo án tự soạn  ", "description": "2 buổi/tuần", "goal_type_id": refs["lose_fat"],
        "difficulty_level_id": refs["beginner"], "duration_weeks": 6,
        "days": [
            {"name": "Thân trên", "exercises": [bench, pulldown]},
            {"name": "Cardio", "notes": "Đi bộ dốc", "exercises": [walk]},
        ],
    }


async def _plan_table_counts(db) -> tuple[int, int, int]:
    """Số dòng của 3 bảng giáo án trong một truy vấn."""
    row = (
        await db.execute(
            text(
                "SELECT (SELECT count(*) FROM training.workout_plans) AS plans,"
                " (SELECT count(*) FROM training.workout_plan_days) AS days,"
                " (SELECT count(*) FROM training.workout_plan_exercises) AS exercises"
            )
        )
    ).one()
    return (row.plans, row.days, row.exercises)


def _created(res: Response) -> dict:
    """201 + `Location` trỏ tới giáo án vừa tạo + đúng KEYS-PLAN/DAY/PEX."""
    assert res.status_code == 201, res.text
    plan = res.json()
    assert res.headers["Location"] == f"{PLANS}/{plan['id']}"
    _assert_plan_shape(plan)
    return plan


async def _plan_rows(db, plan_ids: list[str]) -> tuple[list[Any], list[Any]]:
    """Buổi và bài (qua `db`) của các giáo án, kèm id để so sánh bản nhân bản với mẫu."""
    days = await db.execute(
        text("SELECT plan_id::text, id, day_no, name FROM training.workout_plan_days WHERE plan_id::text = ANY(:ids)"),
        {"ids": plan_ids},
    )
    columns = ", ".join(f"pe.{column}" for column in PEX_COLUMNS)
    exercises = await db.execute(
        text(
            f"SELECT d.plan_id::text, d.day_no, pe.id, pe.order_no, {columns}"
            " FROM training.workout_plan_exercises pe JOIN training.workout_plan_days d ON d.id = pe.plan_day_id"
            " WHERE d.plan_id::text = ANY(:ids)"
        ),
        {"ids": plan_ids},
    )
    return list(days.mappings()), list(exercises.mappings())


def _split_by_plan(rows: list[Any], keys: tuple[str, ...], new_id: str) -> tuple[set, set]:
    new = {tuple(row[key] for key in keys) for row in rows if row["plan_id"] == new_id}
    old = {tuple(row[key] for key in keys) for row in rows if row["plan_id"] == T(2)}
    return new, old


def _assert_same_days_and_exercises(days: list[Any], exercises: list[Any], new_id: str) -> None:
    """Buổi/bài của bản nhân bản giống hệt của T2 (trừ id), và mọi id buổi/bài đều mới."""
    new_days, old_days = _split_by_plan(days, ("day_no", "name"), new_id)
    assert new_days == old_days and len(old_days) == 3
    new_pex, old_pex = _split_by_plan(exercises, ("day_no", "order_no", *PEX_COLUMNS), new_id)
    assert new_pex == old_pex and len(old_pex) == len(exercises) // 2
    for rows in (days, exercises):
        new_ids, old_ids = _split_by_plan(rows, ("id",), new_id)
        assert len(new_ids) == len(old_ids) and not new_ids & old_ids


async def _check_clone_t2_for_newbie(client: AsyncClient, db, headers: dict) -> None:
    """(a) newbie nhân bản T2: tên mặc định, sao chép thuộc tính và toàn bộ buổi/bài; T2 không đổi."""
    t2_sql = text(
        "SELECT name, description, goal_type_id, difficulty_level_id, duration_weeks, updated_at"
        " FROM training.workout_plans WHERE id = :id"
    )
    t2 = (await db.execute(t2_sql, {"id": T(2)})).mappings().one()
    plan = _created(await client.post(PLANS, json={"source_plan_id": T(2)}, headers=headers))
    assert _pick(plan, ("status", "source_plan_id", *PLAN_COLUMNS)) == {
        "status": "active", "source_plan_id": T(2), **{column: t2[column] for column in PLAN_COLUMNS},
    }
    assert plan["name"] == "Push / Pull / Legs"
    owner = await db.scalar(
        text("SELECT owner_user_id::text FROM training.workout_plans WHERE id = :id"), {"id": plan["id"]}
    )
    assert owner == NEWBIE_ID
    _assert_same_days_and_exercises(*await _plan_rows(db, [plan["id"], T(2)]), plan["id"])
    assert (await db.execute(t2_sql, {"id": T(2)})).mappings().one()["updated_at"] == t2["updated_at"]


@pytest.mark.tc("WRT-04")
async def test_create_plan_from_template_copies_days_and_exercises(client: AsyncClient, db, auth_headers):
    await _check_clone_t2_for_newbie(client, db, await auth_headers("newbie"))
    body = {"source_plan_id": T(1), "name": "Full Body của An", "status": "draft"}
    plan = _created(await client.post(PLANS, json=body, headers=await auth_headers("demo")))
    assert (plan["name"], plan["status"], plan["source_plan_id"]) == ("Full Body của An", "draft", T(1))
    assert [len(day["exercises"]) for day in plan["days"]] == [5, 5]


def _assert_custom_plan_exercises(upper: dict, cardio: dict) -> None:
    """Chỉ tiêu từng bài của PLAN-BODY: tạ/RPE/tempo bài 1, tempo null bài 2, cardio theo thời gian."""
    bench, pulldown = upper["exercises"]
    assert bench["exercise"]["slug"] == "barbell-bench-press"
    assert (bench["target_weight_kg"], bench["target_rpe"]) == (60.0, 8.0)
    assert _pick(bench, TEMPO_KEYS) == dict(zip(TEMPO_KEYS, (3, 1, 1, 0), strict=True))
    assert _pick(pulldown, (*TEMPO_KEYS, "notes")) == dict.fromkeys((*TEMPO_KEYS, "notes"))
    walk = cardio["exercises"][0]
    assert (cardio["notes"], walk["target_duration_seconds"], walk["target_reps_min"]) == ("Đi bộ dốc", 1200, None)


@pytest.mark.tc("WRT-05")
async def test_create_custom_plan_assigns_order_and_strips_name(client: AsyncClient, db, auth_headers):
    plan = _created(await client.post(PLANS, json=_plan_body(await _refs(db)), headers=await auth_headers("newbie")))
    assert _pick(plan, ("name", "source_plan_id", "status", "duration_weeks")) == {
        "name": "Giáo án tự soạn", "source_plan_id": None, "status": "active", "duration_weeks": 6,
    }
    upper, cardio = plan["days"]
    assert [day["day_no"] for day in plan["days"]] == [1, 2]
    assert [pex["order_no"] for pex in upper["exercises"]] == [1, 2]
    _assert_custom_plan_exercises(upper, cardio)
    counts = await db.execute(
        text(
            "SELECT count(DISTINCT p.id), count(DISTINCT d.id), count(pe.id)"
            " FROM training.workout_plans p JOIN training.workout_plan_days d ON d.plan_id = p.id"
            " JOIN training.workout_plan_exercises pe ON pe.plan_day_id = d.id WHERE p.owner_user_id = :uid"
        ),
        {"uid": NEWBIE_ID},
    )
    assert tuple(counts.one()) == (1, 2, 3)


def _without(body: dict, key: str) -> dict:
    return {name: value for name, value in body.items() if name != key}


def _with_exercise(body: dict, index: int, **changes: Any) -> dict:
    """PLAN-BODY với bài `index` của buổi 1 đổi theo `changes` (giá trị None = bỏ key)."""
    pex = {**body["days"][0]["exercises"][index], **changes}
    body["days"][0]["exercises"][index] = {key: value for key, value in pex.items() if value is not None}
    return body


async def _invalid_body_cases(db, refs: dict[str, int]) -> list[tuple[dict, str]]:
    """20 ca của WRT-06: (body, field mong đợi; tiền tố `prefix:` = field bắt đầu bằng)."""
    demo_ppl = await db.scalar(
        text("SELECT id::text FROM training.workout_plans WHERE name = 'PPL của An' AND owner_user_id = :uid"),
        {"uid": DEMO_ID},
    )
    body = _plan_body
    return [
        (_without(body(refs), "name"), "name"),
        ({**body(refs), "name": "   "}, "name"),
        (_without(body(refs), "days"), "days"),
        ({**body(refs), "days": []}, "days"),
        ({"source_plan_id": T(7)}, "source_plan_id"),
        ({"source_plan_id": T(8)}, "source_plan_id"),
        ({"source_plan_id": demo_ppl}, "source_plan_id"),
        ({"source_plan_id": "00000000-0000-4000-8000-000000000000"}, "source_plan_id"),
        ({**body(refs), "source_plan_id": T(2)}, "days"),
        ({**body(refs), "status": "archived"}, "status"),
        (_with_exercise(body(refs), 0, target_sets=0), "days.0.exercises.0.target_sets"),
        (_with_exercise(body(refs), 0, target_reps_min=12, target_reps_max=8), "prefix:days.0.exercises.0"),
        (_with_exercise(body(refs), 1, target_reps_min=None, target_reps_max=None), "prefix:days.0.exercises.1"),
        (_with_exercise(body(refs), 1, tempo_eccentric_s=3), "prefix:days.0.exercises.1"),
        (_with_exercise(body(refs), 0, target_rpe=10.5), "days.0.exercises.0.target_rpe"),
        ({**body(refs), "days": [body(refs)["days"][0]] * 32}, "days"),
        ({**body(refs), "days": [{"name": "Thân trên", "exercises": []}]}, "days.0.exercises"),
        ({**body(refs), "goal_type_id": 9999}, "goal_type_id"),
        ({**body(refs), "difficulty_level_id": 9999}, "difficulty_level_id"),
        ({**body(refs), "duration_weeks": 105}, "duration_weeks"),
    ]


def _has_field(fields: list[str | None], expected: str) -> bool:
    if expected.startswith("prefix:"):
        prefix = expected.removeprefix("prefix:")
        return any(field is not None and field.startswith(prefix) for field in fields)
    return expected in fields


@pytest.mark.tc("WRT-06")
async def test_create_plan_invalid_body_returns_422_without_writing(client: AsyncClient, db, auth_headers):
    newbie = await auth_headers("newbie")
    cases = await _invalid_body_cases(db, await _refs(db))
    plans_before = (await _plan_table_counts(db))[0]
    errors = [_err(await client.post(PLANS, json=body, headers=newbie), 422, "validation_error") for body, _ in cases]
    mismatched = [
        (number, _fields(error), expected)
        for number, (error, (_, expected)) in enumerate(zip(errors, cases, strict=True), start=1)
        if not _has_field(_fields(error), expected)
    ]
    assert mismatched == []
    # Ca (5)–(8): cùng message, không lộ giáo án có tồn tại hay không.
    source_errors = errors[4:8]
    assert len({(error["message"], error["details"][0]["message"]) for error in source_errors}) == 1, source_errors
    assert (await _plan_table_counts(db))[0] == plans_before


@pytest.mark.tc("WRT-07")
async def test_create_plan_with_unpublished_exercise_returns_404_and_rolls_back(
    client: AsyncClient, db, auth_headers
):
    newbie = await auth_headers("newbie")
    refs = await _refs(db)
    before = await _plan_table_counts(db)
    for exercise_id in (refs["test-draft-exercise"], refs["test-deleted-exercise"], 999999):
        body = _with_exercise(_plan_body(refs), 1, exercise_id=exercise_id)
        _err(await client.post(PLANS, json=body, headers=newbie), 404, "exercise_not_found")
    assert await _plan_table_counts(db) == before


async def test_create_plan_without_token_or_permission_is_rejected(client: AsyncClient, db, auth_headers):
    body = {"source_plan_id": T(2)}
    before = await _plan_table_counts(db)
    res = await client.post(PLANS, json=body)
    _err(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"
    _err(await client.post(PLANS, json=body, headers=await auth_headers("editor")), 403, "permission_denied")
    assert await _plan_table_counts(db) == before


# --- GET /scheduled-workouts ---
SCHEDULES = "/api/v1/scheduled-workouts"
KEYS_SCHED = {
    "id", "scheduled_date", "title", "notes", "status", "plan_day", "recovery_warning_ack_at", "workout_session_id",
    "is_completed", "created_at",
}
KEYS_SCHED_PLAN_DAY = {"id", "plan_id", "plan_name", "day_no", "name"}
POWER_ID = "5eed0000-0000-4000-8000-000000000004"
PLATEAU_ID = "5eed0000-0000-4000-8000-000000000006"
INPROGRESS_ID = "5eed0000-0000-4000-8000-000000000007"


def _assert_schedule_shape(item: dict) -> None:
    """Đúng KEYS-SCHED, `plan_day` null hoặc đúng 5 key, thời điểm hậu tố Z."""
    _keys(item, KEYS_SCHED)
    assert item["created_at"].endswith("Z"), item
    assert item["recovery_warning_ack_at"] is None or item["recovery_warning_ack_at"].endswith("Z"), item
    if item["plan_day"] is not None:
        _keys(item["plan_day"], KEYS_SCHED_PLAN_DAY)


def _matching(items: list[dict], **expected: Any) -> list[dict]:
    return [item for item in items if all(item[key] == value for key, value in expected.items())]


async def _list_schedules(client: AsyncClient, headers: dict, **params: Any) -> dict:
    return _ok_page(await client.get(SCHEDULES, params=params, headers=headers))


async def _session_links(db, user_id: str) -> dict[str, tuple[str | None, bool]]:
    """Theo `db`: id lịch → (id buổi tập chưa xoá mềm gắn với lịch, buổi đó có `completed` không)."""
    rows = await db.execute(
        text(
            "SELECT sw.id::text AS id, ws.id::text AS session_id, coalesce(ws.status = 'completed', false) AS done"
            " FROM training.scheduled_workouts sw LEFT JOIN training.workout_sessions ws"
            " ON ws.scheduled_workout_id = sw.id AND ws.deleted_at IS NULL WHERE sw.user_id = :uid"
        ),
        {"uid": user_id},
    )
    return {row.id: (row.session_id, row.done) for row in rows}


def _assert_schedule_items(items: list[dict], links: dict[str, tuple[str | None, bool]]) -> None:
    """Mọi phần tử đúng shape, khớp liên kết buổi tập qua `db`; `scheduled_date` không giảm."""
    for item in items:
        _assert_schedule_shape(item)
        assert (item["workout_session_id"], item["is_completed"]) == links[item["id"]], item
    dates = [item["scheduled_date"] for item in items]
    assert dates == sorted(dates)


def _check_demo_special_schedules(items: list[dict]) -> None:
    """Lịch "Tập bù Push" đã xác nhận cảnh báo, một lịch skipped và một lịch cancelled."""
    (makeup,) = _matching(items, title="Tập bù Push")
    assert makeup["recovery_warning_ack_at"] is not None
    assert (makeup["status"], makeup["is_completed"]) == ("planned", False)
    assert _pick(makeup["plan_day"], ("day_no", "name", "plan_name")) == {
        "day_no": 1, "name": "Push – Ngực/Vai/Tay sau", "plan_name": "PPL của An",
    }
    (skipped,) = _matching(items, status="skipped")
    assert _pick(skipped, ("notes", "is_completed", "workout_session_id")) == {
        "notes": "Bận việc đột xuất", "is_completed": False, "workout_session_id": None,
    }
    (cancelled,) = _matching(items, status="cancelled")
    assert cancelled["notes"] == "Đổi lịch"


@pytest.mark.tc("WRT-08")
async def test_list_schedules_demo_returns_all_with_session_links(client: AsyncClient, db, auth_headers):
    body = await _list_schedules(client, await auth_headers("demo"), limit=100)
    assert body["pagination"]["has_more"] is False
    links = await _session_links(db, DEMO_ID)
    assert len(body["data"]) == len(links) == 19
    _assert_schedule_items(body["data"], links)
    _check_demo_special_schedules(body["data"])


async def _collect_pages(client: AsyncClient, headers: dict, limit: int) -> list[dict]:
    """Lần theo `next_cursor` tới trang cuối (giới hạn số trang để test không lặp vô hạn)."""
    pages: list[dict] = []
    params: dict[str, Any] = {"limit": limit}
    for _ in range(50):
        page = await _list_schedules(client, headers, **params)
        pages.append(page)
        if not page["pagination"]["has_more"]:
            return pages
        params["cursor"] = page["pagination"]["next_cursor"]
    raise AssertionError("Quá nhiều trang")


def _merge_full_pages(pages: list[dict], limit: int) -> list[dict]:
    """Mọi trang trừ trang cuối đủ `limit` phần tử và còn trang sau; trang cuối hết. Trả các phần tử gộp."""
    assert len(pages) > 1
    for page in pages[:-1]:
        assert (len(page["data"]), page["pagination"]["has_more"]) == (limit, True)
    assert pages[-1]["pagination"] == {"next_cursor": None, "has_more": False}
    return [item for page in pages for item in page["data"]]


async def _check_power_pagination(client: AsyncClient, db, headers: dict) -> None:
    """(a) limit=40: gộp đủ lịch của power, không trùng, ngày không giảm."""
    items = _merge_full_pages(await _collect_pages(client, headers, 40), 40)
    ids = [item["id"] for item in items]
    assert len(set(ids)) == len(ids) == len(await _session_links(db, POWER_ID))
    dates = [item["scheduled_date"] for item in items]
    assert dates == sorted(dates)


async def _check_demo_date_range(client: AsyncClient, db, headers: dict) -> None:
    """(b) from=D0+7&to=D0+13 (tính cả hai đầu), D0 = ngày lịch sớm nhất của demo."""
    row = (
        await db.execute(
            text(
                "WITH d AS (SELECT min(scheduled_date) AS d0 FROM training.scheduled_workouts WHERE user_id = :uid)"
                " SELECT d.d0 + 7 AS lo, d.d0 + 13 AS hi, (SELECT count(*) FROM training.scheduled_workouts sw"
                " WHERE sw.user_id = :uid AND sw.scheduled_date BETWEEN d.d0 + 7 AND d.d0 + 13) AS n FROM d"
            ),
            {"uid": DEMO_ID},
        )
    ).one()
    lo, hi = row.lo.isoformat(), row.hi.isoformat()
    items = (await _list_schedules(client, headers, **{"from": lo, "to": hi}))["data"]
    assert len(items) == row.n > 0
    assert all(lo <= item["scheduled_date"] <= hi for item in items)


async def _inprogress_linked_schedules(db) -> dict[str, str]:
    """Theo `db`: tên và trạng thái buổi tập của inprogress → id lịch gắn với buổi đó."""
    rows = await db.execute(
        text(
            "SELECT scheduled_workout_id::text AS sid, name, status::text AS status FROM training.workout_sessions"
            " WHERE user_id = :uid AND scheduled_workout_id IS NOT NULL AND deleted_at IS NULL"
        ),
        {"uid": INPROGRESS_ID},
    )
    linked: dict[str, str] = {}
    for row in rows:
        linked[row.name] = row.sid
        linked[row.status] = row.sid
    return linked


async def _check_inprogress_sessions(client: AsyncClient, db, headers: dict) -> None:
    """(d) Lịch gắn buổi in_progress/abandoned chưa hoàn thành; lịch gắn buổi completed thì hoàn thành."""
    items = {item["id"]: item for item in (await _list_schedules(client, headers, limit=100))["data"]}
    linked = await _inprogress_linked_schedules(db)
    running, abandoned, done = items[linked["Circuit B"]], items[linked["abandoned"]], items[linked["Circuit A"]]
    assert running["workout_session_id"] is not None and running["is_completed"] is False
    assert abandoned["workout_session_id"] is not None and abandoned["is_completed"] is False
    assert done["is_completed"] is True
    (cancelled,) = _matching(list(items.values()), status="cancelled")
    assert cancelled["notes"] == "Bận họp"


@pytest.mark.tc("WRT-09")
async def test_list_schedules_paginate_and_filter(client: AsyncClient, db, auth_headers):
    await _check_power_pagination(client, db, await auth_headers("power"))
    demo = await auth_headers("demo")
    await _check_demo_date_range(client, db, demo)
    skipped = _only_item(await _list_schedules(client, demo, status="skipped"))
    assert skipped["status"] == "skipped"
    await _check_inprogress_sessions(client, db, await auth_headers("inprogress"))


@pytest.mark.tc("WRT-10")
async def test_list_schedules_invalid_query_returns_422_and_no_schedule_returns_empty(
    client: AsyncClient, auth_headers
):
    demo = await auth_headers("demo")
    cases = [
        ({"from": "2026-13-01"}, "from"),
        ({"from": "2026-05-10", "to": "2026-05-09"}, "to"),
        ({"limit": 0}, "limit"),
        ({"limit": 101}, "limit"),
        ({"cursor": "!!!khong-phai-cursor"}, "cursor"),
        ({"status": "completed"}, "status"),
    ]
    fields = [
        _fields(_err(await client.get(SCHEDULES, params=params, headers=demo), 422, "validation_error"))
        for params, _ in cases
    ]
    assert fields == [[field] for _, field in cases]
    empty = await _list_schedules(client, await auth_headers("newbie"))
    assert empty == {"data": [], "pagination": {"next_cursor": None, "has_more": False}}


async def test_list_schedules_with_foreign_cursor_returns_422(client: AsyncClient, auth_headers):
    res = await client.get(SCHEDULES, params={"cursor": encode_cursor({"foo": 1})}, headers=await auth_headers())
    assert _fields(_err(res, 422, "validation_error")) == ["cursor"]


async def test_list_schedules_without_token_or_permission_is_rejected(client: AsyncClient, auth_headers):
    res = await client.get(SCHEDULES)
    _err(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"
    _err(await client.get(SCHEDULES, headers=await auth_headers("editor")), 403, "permission_denied")


# --- POST /scheduled-workouts ---
async def _today(db, user_id: str, offset: int = 0) -> str:
    """TODAY (+ offset ngày) theo múi giờ của user ở auth.user_profiles, dạng YYYY-MM-DD."""
    day = await db.scalar(
        text(
            "SELECT (now() AT TIME ZONE timezone)::date + CAST(:offset AS integer)"
            " FROM auth.user_profiles WHERE user_id = :uid"
        ),
        {"uid": user_id, "offset": offset},
    )
    return day.isoformat()


async def _plan_day_id(db, plan_name: str, owner_id: str | None, day_no: int) -> str:
    """ID buổi giáo án theo (tên giáo án, chủ sở hữu; None = giáo án mẫu, day_no)."""
    day_id = await db.scalar(
        text(
            "SELECT d.id::text FROM training.workout_plan_days d JOIN training.workout_plans p ON p.id = d.plan_id"
            " WHERE p.name = :name AND p.owner_user_id IS NOT DISTINCT FROM CAST(:owner AS uuid) AND d.day_no = :day"
        ),
        {"name": plan_name, "owner": owner_id, "day": day_no},
    )
    assert day_id is not None, (plan_name, owner_id, day_no)
    return day_id


async def _schedule_count(db) -> int:
    return await db.scalar(text("SELECT count(*) FROM training.scheduled_workouts"))


async def _created_schedule(db, res: Response, user_id: str, scheduled_date: str) -> dict:
    """201 + `Location` + KEYS-SCHED + mặc định của lịch mới; qua `db`: đúng user và ngày."""
    assert res.status_code == 201, res.text
    item = res.json()
    assert res.headers["Location"] == f"{SCHEDULES}/{item['id']}"
    _assert_schedule_shape(item)
    assert _pick(item, ("status", "is_completed", "workout_session_id", "recovery_warning_ack_at")) == {
        "status": "planned", "is_completed": False, "workout_session_id": None, "recovery_warning_ack_at": None,
    }
    row = (
        await db.execute(
            text("SELECT user_id::text AS uid, scheduled_date FROM training.scheduled_workouts WHERE id = :id"),
            {"id": item["id"]},
        )
    ).one()
    assert (row.uid, row.scheduled_date.isoformat()) == (user_id, scheduled_date)
    assert item["scheduled_date"] == scheduled_date
    return item


async def _check_demo_free_schedule(client: AsyncClient, db, headers: dict) -> None:
    """(a) Buổi tự do: title đã strip, không có plan_day."""
    today = await _today(db, DEMO_ID)
    body = {"scheduled_date": today, "title": "  Chạy bộ công viên ", "notes": "5 km"}
    item = await _created_schedule(db, await client.post(SCHEDULES, json=body, headers=headers), DEMO_ID, today)
    assert _pick(item, ("title", "plan_day", "notes")) == {"title": "Chạy bộ công viên", "plan_day": None, "notes": "5 km"}


async def _check_demo_plan_day_schedule(client: AsyncClient, db, headers: dict) -> None:
    """(b) Buổi 3 của "PPL của An": plan_day đủ thông tin buổi và giáo án."""
    day = await _today(db, DEMO_ID, 2)
    legs = await _plan_day_id(db, "PPL của An", DEMO_ID, 3)
    res = await client.post(SCHEDULES, json={"scheduled_date": day, "plan_day_id": legs}, headers=headers)
    item = await _created_schedule(db, res, DEMO_ID, day)
    plan_id = await db.scalar(text("SELECT plan_id::text FROM training.workout_plan_days WHERE id = :id"), {"id": legs})
    assert item["title"] is None
    assert item["plan_day"] == {
        "id": legs, "plan_id": plan_id, "plan_name": "PPL của An", "day_no": 3, "name": "Legs – Chân/Mông",
    }


@pytest.mark.tc("WRT-11")
async def test_create_schedule_free_or_from_plan_day_returns_201(client: AsyncClient, db, auth_headers):
    demo = await auth_headers("demo")
    await _check_demo_free_schedule(client, db, demo)
    await _check_demo_plan_day_schedule(client, db, demo)
    day = await _today(db, NEWBIE_ID, 1)
    t1_name = await db.scalar(text("SELECT name FROM training.workout_plans WHERE id = :id"), {"id": T(1)})
    body = {"scheduled_date": day, "plan_day_id": await _plan_day_id(db, t1_name, None, 1)}
    res = await client.post(SCHEDULES, json=body, headers=await auth_headers("newbie"))
    item = await _created_schedule(db, res, NEWBIE_ID, day)
    assert (item["plan_day"]["plan_id"], item["plan_day"]["plan_name"]) == (T(1), "Full Body cho người mới")


async def _invalid_plan_day_cases(db) -> list[tuple[str, dict, str]]:
    """Ca (3)–(7) của WRT-13: buổi giáo án không dùng được, ngày = TODAY của persona gửi."""
    t7_name = await db.scalar(text("SELECT name FROM training.workout_plans WHERE id = :id"), {"id": T(7)})
    plan_days = [
        ("demo", DEMO_ID, await _plan_day_id(db, "Upper/Lower của Bình", POWER_ID, 1)),
        ("demo", DEMO_ID, "00000000-0000-4000-8000-000000000000"),
        ("demo", DEMO_ID, await _plan_day_id(db, t7_name, None, 1)),
        ("power", POWER_ID, await _plan_day_id(db, "PPL (giai đoạn trước)", POWER_ID, 1)),
        ("plateau", PLATEAU_ID, await _plan_day_id(db, "Nháp – bỏ", PLATEAU_ID, 1)),
    ]
    return [
        (persona, {"scheduled_date": await _today(db, user_id), "plan_day_id": day_id}, "plan_day_id")
        for persona, user_id, day_id in plan_days
    ]


async def _invalid_schedule_cases(db) -> list[tuple[str, dict, str]]:
    """12 ca của WRT-13: (persona, body, field mong đợi)."""
    today = await _today(db, DEMO_ID)
    return [
        ("demo", {"scheduled_date": today}, "plan_day_id"),
        ("demo", {"scheduled_date": await _today(db, DEMO_ID, -1), "title": "x"}, "scheduled_date"),
        *await _invalid_plan_day_cases(db),
        ("demo", {"scheduled_date": today, "title": "x" * 151}, "title"),
        ("demo", {"scheduled_date": today, "title": "x", "notes": "n" * 501}, "notes"),
        ("demo", {"scheduled_date": "2026-02-30", "title": "x"}, "scheduled_date"),
        ("demo", {"scheduled_date": today, "plan_day_id": "abc"}, "plan_day_id"),
        (
            "demo",
            {"scheduled_date": today, "title": "x", "acknowledge_recovery_warning": "maybe"},
            "acknowledge_recovery_warning",
        ),
    ]


def _plan_day_messages(error: dict) -> tuple[str, tuple[str, ...]]:
    return error["message"], tuple(d["message"] for d in error["details"] if d["field"] == "plan_day_id")


@pytest.mark.tc("WRT-13")
async def test_create_schedule_invalid_body_returns_422_without_writing(client: AsyncClient, db, auth_headers):
    cases = await _invalid_schedule_cases(db)
    headers = {persona: await auth_headers(persona) for persona in ("demo", "power", "plateau")}
    before = await _schedule_count(db)
    errors = [
        _err(await client.post(SCHEDULES, json=body, headers=headers[persona]), 422, "validation_error")
        for persona, body, _ in cases
    ]
    mismatched = [
        (number, _fields(error), expected)
        for number, (error, (_, _, expected)) in enumerate(zip(errors, cases, strict=True), start=1)
        if expected not in _fields(error)
    ]
    assert mismatched == []
    # Ca (3), (4), (5): cùng message, không lộ buổi giáo án có tồn tại hay thuộc ai.
    assert len({_plan_day_messages(error) for error in errors[2:5]}) == 1, errors[2:5]
    assert await _schedule_count(db) == before


async def test_create_schedule_without_token_or_permission_is_rejected(client: AsyncClient, db, auth_headers):
    body = {"scheduled_date": await _today(db, DEMO_ID), "title": "x"}
    before = await _schedule_count(db)
    res = await client.post(SCHEDULES, json=body)
    _err(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"
    _err(await client.post(SCHEDULES, json=body, headers=await auth_headers("editor")), 403, "permission_denied")
    assert await _schedule_count(db) == before


# --- GET /recovery/muscle-groups (Heatmap) ---
MUSCLES = "/api/v1/recovery/muscle-groups"
PREDICTIONS = "/api/v1/recovery/predictions"
KEYS_MRS = {
    "muscle_group_id", "muscle_code", "muscle_name", "heatmap_region_key", "recovery_status", "recovery_pct",
    "remaining_hours", "fatigue_score", "last_trained_at", "recovered_at", "last_session_id", "model_version",
}
KEYS_PRED = {
    "session_id", "session_name", "trained_at", "muscle_group_id", "muscle_code", "muscle_name", "model_version",
    "fatigue_score", "recovered_at", "predicted_at",
}
READY_NO_DATA = {
    "recovery_status": "ready", "recovery_pct": 100, "remaining_hours": 0.0, "fatigue_score": None,
    "last_trained_at": None, "recovered_at": None, "last_session_id": None, "model_version": None,
}
NO_TIME = timedelta(0)


async def _muscle_ids(db) -> dict[str, int]:
    """Mọi nhóm cơ: code → id (đọc qua `db`, không hard-code ID)."""
    rows = await db.execute(text("SELECT code, id FROM catalog.muscle_groups"))
    return {row.code: row.id for row in rows}


async def _heatmap_codes(db) -> set[str]:
    rows = await db.execute(text("SELECT code FROM catalog.muscle_groups WHERE heatmap_region_key IS NOT NULL"))
    return {row.code for row in rows}


async def _insert_session(db, user_id: str, ended_ago: timedelta, name: str = "Phục hồi test") -> str:
    """Buổi `completed` kết thúc lúc now() - ended_ago, bắt đầu trước đó 1 giờ; trả id."""
    return await db.scalar(
        text(
            "INSERT INTO training.workout_sessions (user_id, name, status, started_at, ended_at)"
            " VALUES (:uid, :name, 'completed', now() - CAST(:ago AS interval) - interval '1 hour',"
            " now() - CAST(:ago AS interval)) RETURNING id::text"
        ),
        {"uid": user_id, "name": name, "ago": ended_ago},
    )


async def _soft_delete_session(db, session_id: str) -> None:
    await db.execute(text("UPDATE training.workout_sessions SET deleted_at = now() WHERE id = :id"), {"id": session_id})


async def _predict(db, session_id: str, muscle_group_id: int, values: tuple[str, float, timedelta, timedelta]) -> None:
    """Một dự đoán: (model_version, fatigue_score, recovered_at - now(), now() - predicted_at)."""
    version, fatigue, recovered_in, predicted_ago = values
    await db.execute(
        text(
            "INSERT INTO training.recovery_predictions"
            " (session_id, muscle_group_id, model_version, fatigue_score, recovered_at, predicted_at)"
            " VALUES (:sid, :mid, :version, :fatigue, now() + CAST(:recovered_in AS interval),"
            " now() - CAST(:predicted_ago AS interval))"
        ),
        {
            "sid": session_id, "mid": muscle_group_id, "version": version, "fatigue": fatigue,
            "recovered_in": recovered_in, "predicted_ago": predicted_ago,
        },
    )


async def _ended_at(db, session_id: str) -> datetime:
    return await db.scalar(text("SELECT ended_at FROM training.workout_sessions WHERE id = :id"), {"id": session_id})


def _parse_ts(value: str) -> datetime:
    """Thời điểm ISO-8601 UTC hậu tố Z → datetime có múi giờ."""
    assert value.endswith("Z"), value
    return datetime.fromisoformat(value)


def _by_code(items: list[dict]) -> dict[str, dict]:
    return {item["muscle_code"]: item for item in items}


async def _get_page(client: AsyncClient, url: str, headers: dict, **params: Any) -> dict:
    return _ok_page(await client.get(url, params=params, headers=headers))


async def _follow_pages(client: AsyncClient, url: str, headers: dict, limit: int) -> list[dict]:
    """Lần theo `next_cursor` tới trang cuối (giới hạn số trang để test không lặp vô hạn)."""
    pages: list[dict] = []
    params: dict[str, Any] = {"limit": limit}
    for _ in range(50):
        page = await _get_page(client, url, headers, **params)
        pages.append(page)
        if not page["pagination"]["has_more"]:
            return pages
        params["cursor"] = page["pagination"]["next_cursor"]
    raise AssertionError("Quá nhiều trang")


def _assert_all_ready(items: list[dict], heatmap_codes: set[str]) -> None:
    """Đủ nhóm cơ có Heatmap, đúng KEYS-MRS, ID số nguyên tăng dần, tất cả `ready` và chưa có dữ liệu."""
    assert len(items) == len(heatmap_codes) == 18
    assert {item["muscle_code"] for item in items} == heatmap_codes
    ids = [item["muscle_group_id"] for item in items]
    assert all(type(mid) is int for mid in ids) and ids == sorted(set(ids))
    for item in items:
        _keys(item, KEYS_MRS)
        assert _pick(item, tuple(READY_NO_DATA)) == READY_NO_DATA, item


@pytest.mark.tc("WRT-14")
async def test_list_muscle_recovery_without_predictions_returns_all_ready(client: AsyncClient, db, auth_headers):
    heatmap_codes = await _heatmap_codes(db)
    body = await _get_page(client, MUSCLES, await auth_headers("demo"))
    assert body["pagination"] == {"next_cursor": None, "has_more": False}
    _assert_all_ready(body["data"], heatmap_codes)
    chest = _by_code(body["data"])["chest"]
    assert _pick(chest, ("muscle_name", "heatmap_region_key")) == {"muscle_name": "Ngực", "heatmap_region_key": "chest"}
    newbie = await _get_page(client, MUSCLES, await auth_headers("newbie"))
    assert newbie["pagination"] == {"next_cursor": None, "has_more": False}
    _assert_all_ready(newbie["data"], heatmap_codes)


async def _seed_heatmap_predictions(db) -> str:
    """Dữ liệu WRT-15: buổi S của demo + buổi đã xoá của demo + buổi của power; trả id buổi S."""
    ids = await _muscle_ids(db)
    session = await _insert_session(db, DEMO_ID, timedelta(hours=1))
    for code, fatigue, recovered_in in (
        ("chest", 80, timedelta(hours=59)), ("triceps", 45, timedelta(hours=1)), ("front_delts", 30, timedelta(hours=-1)),
    ):
        await _predict(db, session, ids[code], ("test-v1", fatigue, recovered_in, NO_TIME))
    deleted = await _insert_session(db, DEMO_ID, timedelta(minutes=30))
    await _soft_delete_session(db, deleted)
    await _predict(db, deleted, ids["quads"], ("test-v1", 90, timedelta(hours=70), NO_TIME))
    foreign = await _insert_session(db, POWER_ID, timedelta(hours=1))
    await _predict(db, foreign, ids["lats"], ("test-v1", 90, timedelta(hours=70), NO_TIME))
    return session


def _check_heatmap_with_predictions(items: list[dict], session: str) -> None:
    """(a) chest fatigued, triceps recovering, front_delts đã hồi phục; quads/lats không lấy dự đoán nào."""
    by_code = _by_code(items)
    assert _pick(by_code["chest"], ("recovery_status", "recovery_pct", "remaining_hours", "fatigue_score")) == {
        "recovery_status": "fatigued", "recovery_pct": 2, "remaining_hours": 59.0, "fatigue_score": 80.0,
    }
    assert _pick(by_code["chest"], ("last_session_id", "model_version")) == {
        "last_session_id": session, "model_version": "test-v1",
    }
    assert _pick(by_code["triceps"], ("recovery_status", "recovery_pct", "remaining_hours")) == {
        "recovery_status": "recovering", "recovery_pct": 50, "remaining_hours": 1.0,
    }
    assert _pick(by_code["front_delts"], ("recovery_status", "recovery_pct")) == {
        "recovery_status": "ready", "recovery_pct": 100,
    }
    for code in ("quads", "lats"):
        assert _pick(by_code[code], ("recovery_status", "last_session_id")) == {
            "recovery_status": "ready", "last_session_id": None,
        }


async def _codes_with_status(client: AsyncClient, headers: dict, status: str) -> list[str]:
    items = (await _get_page(client, MUSCLES, headers, recovery_status=status))["data"]
    assert all(item["recovery_status"] == status for item in items), items
    return [item["muscle_code"] for item in items]


@pytest.mark.tc("WRT-15")
async def test_list_muscle_recovery_uses_latest_own_predictions_and_filters(client: AsyncClient, db, auth_headers):
    session = await _seed_heatmap_predictions(db)
    demo = await auth_headers("demo")
    items = (await _get_page(client, MUSCLES, demo))["data"]
    for item in items:
        _keys(item, KEYS_MRS)
    _check_heatmap_with_predictions(items, session)
    chest = _by_code(items)["chest"]
    assert _parse_ts(chest["last_trained_at"]) == await _ended_at(db, session)
    assert _parse_ts(chest["recovered_at"]) > _parse_ts(chest["last_trained_at"])
    assert await _codes_with_status(client, demo, "fatigued") == ["chest"]
    assert await _codes_with_status(client, demo, "recovering") == ["triceps"]
    ready = await _codes_with_status(client, demo, "ready")
    assert len(ready) == len(await _heatmap_codes(db)) - 2 == 16
    assert not {"chest", "triceps"} & set(ready)


async def _assert_invalid_queries(client: AsyncClient, url: str, headers: dict, cases: list[tuple[dict, str]]) -> None:
    """Mỗi ca (params, field) trả 422 validation_error với đúng một lỗi gắn field đó."""
    fields = [
        _fields(_err(await client.get(url, params=params, headers=headers), 422, "validation_error"))
        for params, _ in cases
    ]
    assert fields == [[field] for _, field in cases]


async def _check_muscle_pagination(client: AsyncClient, headers: dict) -> None:
    """(a) limit=5: các trang 5, 5, 5, 3; gộp được 18 nhóm cơ không trùng, ID tăng dần."""
    pages = await _follow_pages(client, MUSCLES, headers, 5)
    assert [len(page["data"]) for page in pages] == [5, 5, 5, 3]
    assert [page["pagination"]["has_more"] for page in pages] == [True, True, True, False]
    assert pages[-1]["pagination"]["next_cursor"] is None
    ids = [item["muscle_group_id"] for page in pages for item in page["data"]]
    assert len(ids) == len(set(ids)) == 18 and ids == sorted(ids)


@pytest.mark.tc("WRT-16")
async def test_list_muscle_recovery_paginates_and_rejects_invalid_query(client: AsyncClient, auth_headers):
    demo = await auth_headers("demo")
    await _check_muscle_pagination(client, demo)
    cases = [
        ({"limit": 0}, "limit"),
        ({"limit": 101}, "limit"),
        ({"cursor": "!!!khong-phai-cursor"}, "cursor"),
        ({"cursor": encode_cursor({"foo": 1})}, "cursor"),
        ({"recovery_status": "red"}, "recovery_status"),
    ]
    await _assert_invalid_queries(client, MUSCLES, demo, cases)


async def test_list_muscle_recovery_with_wrong_cursor_type_returns_422(client: AsyncClient, auth_headers):
    demo = await auth_headers("demo")
    for value in ("5", True, 1.5, None, 99999):
        res = await client.get(MUSCLES, params={"cursor": encode_cursor({"muscle_group_id": value})}, headers=demo)
        assert _fields(_err(res, 422, "validation_error")) == ["cursor"], value


async def test_list_muscle_recovery_without_token_or_permission_is_rejected(client: AsyncClient, auth_headers):
    res = await client.get(MUSCLES)
    _err(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"
    _err(await client.get(MUSCLES, headers=await auth_headers("editor")), 403, "permission_denied")


# --- GET /recovery/predictions ---
async def _seed_prediction_history(db) -> dict[str, str]:
    """Dữ liệu WRT-17: buổi A, B của demo; C của demo đã xoá; D của power. Trả tên buổi → id."""
    ids = await _muscle_ids(db)
    sessions = {
        "A": await _insert_session(db, DEMO_ID, timedelta(hours=50), "A"),
        "B": await _insert_session(db, DEMO_ID, timedelta(hours=1), "B"),
        "C": await _insert_session(db, DEMO_ID, timedelta(hours=2), "C"),
        "D": await _insert_session(db, POWER_ID, timedelta(hours=1), "D"),
    }
    await _soft_delete_session(db, sessions["C"])
    predictions = [
        ("A", "chest", ("test-v1", 70, timedelta(hours=10), NO_TIME)),
        ("A", "triceps", ("test-v1", 40, timedelta(hours=-20), NO_TIME)),
        ("B", "chest", ("test-v1", 80, timedelta(hours=59), timedelta(minutes=10))),
        ("B", "chest", ("test-v2", 85, timedelta(hours=60), NO_TIME)),
        ("C", "quads", ("test-v1", 90, timedelta(hours=70), NO_TIME)),
        ("D", "lats", ("test-v1", 90, timedelta(hours=70), NO_TIME)),
    ]
    for name, code, values in predictions:
        await _predict(db, sessions[name], ids[code], values)
    return sessions


def _pairs(items: list[dict]) -> list[tuple[str, str]]:
    return [(item["session_id"], item["muscle_code"]) for item in items]


def _assert_prediction_shape(items: list[dict], ids: dict[str, int]) -> None:
    """Đúng KEYS-PRED, ID nhóm cơ là số nguyên khớp `code`, thời điểm hậu tố Z."""
    for item in items:
        _keys(item, KEYS_PRED)
        assert item["muscle_group_id"] == ids[item["muscle_code"]] and type(item["muscle_group_id"]) is int
        for key in ("trained_at", "recovered_at", "predicted_at"):
            _parse_ts(item[key])


async def _check_latest_b_chest(db, item: dict, session_b: str) -> None:
    """(B, chest) là bản `predicted_at` mới nhất (test-v2)."""
    assert _pick(item, ("model_version", "fatigue_score", "session_name")) == {
        "model_version": "test-v2", "fatigue_score": 85.0, "session_name": "B",
    }
    assert _parse_ts(item["trained_at"]) == await _ended_at(db, session_b)


@pytest.mark.tc("WRT-17")
async def test_list_predictions_returns_latest_per_session_and_muscle(client: AsyncClient, db, auth_headers):
    sessions = await _seed_prediction_history(db)
    ids = await _muscle_ids(db)
    a, b = sessions["A"], sessions["B"]
    demo = await auth_headers("demo")
    items = (await _get_page(client, PREDICTIONS, demo))["data"]
    _assert_prediction_shape(items, ids)
    assert _pairs(items) == [(b, "chest"), (a, "chest"), (a, "triceps")]
    await _check_latest_b_chest(db, items[0], b)
    assert not {sessions["C"], sessions["D"]} & {item["session_id"] for item in items}
    chest_only = (await _get_page(client, PREDICTIONS, demo, muscle_group_id=ids["chest"]))["data"]
    assert _pairs(chest_only) == [(b, "chest"), (a, "chest")]
    pages = await _follow_pages(client, PREDICTIONS, demo, 2)
    assert [(len(page["data"]), page["pagination"]["has_more"]) for page in pages] == [(2, True), (1, False)]
    assert pages[-1]["pagination"]["next_cursor"] is None
    assert _pairs(pages[-1]["data"]) == [(a, "triceps")]


@pytest.mark.tc("WRT-18")
async def test_list_predictions_invalid_query_returns_422_and_no_data_returns_empty(client: AsyncClient, auth_headers):
    demo = await auth_headers("demo")
    cases = [
        ({"limit": 0}, "limit"),
        ({"limit": 101}, "limit"),
        ({"cursor": "!!!khong-phai-cursor"}, "cursor"),
        ({"muscle_group_id": "abc"}, "muscle_group_id"),
        ({"muscle_group_id": 0}, "muscle_group_id"),
    ]
    await _assert_invalid_queries(client, PREDICTIONS, demo, cases)
    empty = {"data": [], "pagination": {"next_cursor": None, "has_more": False}}
    assert await _get_page(client, PREDICTIONS, demo, muscle_group_id=9999) == empty
    assert await _get_page(client, PREDICTIONS, await auth_headers("newbie")) == empty


async def test_list_predictions_with_foreign_cursor_returns_422(client: AsyncClient, auth_headers):
    demo = await auth_headers("demo")
    bad_cursors = [
        {"foo": 1},
        {"trained_at": "2026-11-27T00:00:00", "session_id": DEMO_ID, "muscle_group_id": 1},
        {"trained_at": "2026-11-27T00:00:00+00:00", "session_id": 1, "muscle_group_id": 1},
        {"trained_at": "2026-11-27T00:00:00+00:00", "session_id": DEMO_ID, "muscle_group_id": True},
    ]
    for values in bad_cursors:
        res = await client.get(PREDICTIONS, params={"cursor": encode_cursor(values)}, headers=demo)
        assert _fields(_err(res, 422, "validation_error")) == ["cursor"], values


async def test_list_predictions_without_token_or_permission_is_rejected(client: AsyncClient, auth_headers):
    res = await client.get(PREDICTIONS)
    _err(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"
    _err(await client.get(PREDICTIONS, headers=await auth_headers("editor")), 403, "permission_denied")


# --- POST /workout-sessions/{session_id}/predict-recovery ---
SESSIONS = "/api/v1/workout-sessions"
KEYS_PREDICT = {"session_id", "model_version", "predictions"}
ZERO_UUID = "00000000-0000-4000-8000-000000000000"
LATEST_COMPLETED_SQL = (
    "SELECT id::text FROM training.workout_sessions WHERE user_id = :uid AND status = 'completed'"
    " AND deleted_at IS NULL ORDER BY started_at DESC LIMIT 1"
)


class _FakeRecoveryAi:
    """Thay `recovery_ai_client.predict_recovery`: ghi lại payload, trả `output` hoặc ném `error`."""

    def __init__(self) -> None:
        self.calls: list[RecoveryPredictionInput] = []
        self.output: dict | None = None
        self.error: Exception | None = None

    async def __call__(self, payload: RecoveryPredictionInput) -> RecoveryPredictionOutput:
        self.calls.append(payload)
        if self.error is not None:
            raise self.error
        return RecoveryPredictionOutput.model_validate(self.output)


@pytest.fixture
def fake_ai(monkeypatch) -> _FakeRecoveryAi:
    fake = _FakeRecoveryAi()
    monkeypatch.setattr(recovery_ai_client, "predict_recovery", fake)
    return fake


async def _finish(client: AsyncClient, headers: dict, session_id: str) -> datetime:
    res = await client.post(f"{SESSIONS}/{session_id}/finish", json={}, headers=headers)
    assert res.status_code == 200, res.text
    return _parse_ts(res.json()["ended_at"])


async def _start(client: AsyncClient, headers: dict, name: str) -> str:
    res = await client.post(SESSIONS, json={"name": name}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _bench_session(client: AsyncClient, db, headers: dict) -> tuple[str, datetime]:
    """BENCH-SESSION: barbell-bench-press 3 hiệp 8 × 60 kg rồi kết thúc; trả (id, ended_at)."""
    session_id = await _start(client, headers, "Ngực test")
    bench = await db.scalar(text("SELECT id FROM catalog.exercises WHERE slug = 'barbell-bench-press'"))
    res = await client.post(
        f"{SESSIONS}/{session_id}/exercises", json={"exercise_id": bench, "added_via": "wiki"}, headers=headers
    )
    assert res.status_code == 201, res.text
    sets_url = f"{SESSIONS}/{session_id}/exercises/{res.json()['id']}/sets"
    for _ in range(3):
        res = await client.post(sets_url, json={"reps": 8, "weight_kg": 60}, headers=headers)
        assert res.status_code == 201, res.text
    return session_id, await _finish(client, headers, session_id)


def _ai_output(ids: dict[str, int], ended_at: datetime, chest_fatigue: float = 72.5) -> dict:
    """Kết quả AI giả của WRT-19: chest, triceps, front_delts, mốc hồi phục tính từ lúc kết thúc buổi."""
    rows = (("chest", chest_fatigue, 60), ("triceps", 40.0, 36), ("front_delts", 35.0, 30))
    return {
        "model_version": "recovery-test-1",
        "predictions": [
            {"muscle_group_id": ids[code], "fatigue_score": fatigue, "recovered_at": ended_at + timedelta(hours=hours)}
            for code, fatigue, hours in rows
        ],
    }


async def _predict_recovery(client: AsyncClient, headers: dict, session_id: str) -> Response:
    return await client.post(f"{SESSIONS}/{session_id}/predict-recovery", headers=headers)


async def _prediction_rows(db, session_id: str) -> dict[int, float]:
    rows = await db.execute(
        text("SELECT muscle_group_id, fatigue_score FROM training.recovery_predictions WHERE session_id = :sid"),
        {"sid": session_id},
    )
    return {row.muscle_group_id: float(row.fatigue_score) for row in rows}


async def _prediction_count(db) -> int:
    return await db.scalar(text("SELECT count(*) FROM training.recovery_predictions"))


async def _view_loads(db, session_id: str) -> dict[int, dict]:
    """Tải theo nhóm cơ của buổi, đọc thẳng view + base_recovery_hours (đối chiếu payload gửi AI)."""
    rows = await db.execute(
        text(
            "SELECT l.muscle_group_id, l.direct_sets, l.effective_sets, l.total_reps, l.weighted_volume_kg,"
            " l.avg_rpe, mg.base_recovery_hours FROM training.v_session_muscle_load l"
            " JOIN catalog.muscle_groups mg ON mg.id = l.muscle_group_id WHERE l.session_id = :sid"
        ),
        {"sid": session_id},
    )
    loads: dict[int, dict] = {}
    for row in rows.mappings():
        load = {key: (float(value) if isinstance(value, Decimal) else value) for key, value in row.items()}
        loads[load["muscle_group_id"]] = load
    return loads


async def _check_ai_payload(db, payload: RecoveryPredictionInput, session_id: str, ended_at: datetime) -> None:
    """Payload gửi AI: đúng buổi, đúng user, `trained_at` = ended_at, tải khớp từng dòng của view."""
    assert (str(payload.session_id), str(payload.user_id), payload.trained_at) == (session_id, DEMO_ID, ended_at)
    sent = {load.muscle_group_id: load.model_dump() for load in payload.muscle_loads}
    assert len(sent) == len(payload.muscle_loads)
    assert sent == await _view_loads(db, session_id)
    chest = sent[(await _muscle_ids(db))["chest"]]
    assert _pick(chest, ("direct_sets", "total_reps", "weighted_volume_kg", "base_recovery_hours")) == {
        "direct_sets": 3, "total_reps": 24, "weighted_volume_kg": 1440.0, "base_recovery_hours": 60,
    }


def _check_predict_body(body: dict, session_id: str, ids: dict[str, int], ended_at: datetime) -> None:
    """(a) Đúng 3 key, 3 dự đoán đúng KEYS-PRED của buổi, sắp muscle_group_id tăng dần."""
    _keys(body, KEYS_PREDICT)
    assert (body["session_id"], body["model_version"]) == (session_id, "recovery-test-1")
    items = body["predictions"]
    _assert_prediction_shape(items, ids)
    assert [item["muscle_group_id"] for item in items] == sorted(ids[c] for c in ("chest", "triceps", "front_delts"))
    assert {(item["session_id"], item["model_version"]) for item in items} == {(session_id, "recovery-test-1")}
    chest = _by_code(items)["chest"]
    assert chest["fatigue_score"] == 72.5
    assert _parse_ts(chest["recovered_at"]) == ended_at + timedelta(hours=60)


@pytest.mark.tc("WRT-19")
async def test_predict_recovery_completed_session_calls_ai_and_upserts(
    client: AsyncClient, db, auth_headers, fake_ai: _FakeRecoveryAi
):
    demo = await auth_headers("demo")
    ids = await _muscle_ids(db)
    session_id, ended_at = await _bench_session(client, db, demo)
    fake_ai.output = _ai_output(ids, ended_at)
    res = await _predict_recovery(client, demo, session_id)
    assert res.status_code == 200, res.text
    _check_predict_body(res.json(), session_id, ids, ended_at)
    assert len(fake_ai.calls) == 1
    await _check_ai_payload(db, fake_ai.calls[0], session_id, ended_at)
    assert len(await _prediction_rows(db, session_id)) == 3

    fake_ai.output = _ai_output(ids, ended_at, chest_fatigue=65.0)
    res = await _predict_recovery(client, demo, session_id)
    assert res.status_code == 200, res.text
    assert _by_code(res.json()["predictions"])["chest"]["fatigue_score"] == 65.0
    stored = await _prediction_rows(db, session_id)
    assert len(stored) == 3 and stored[ids["chest"]] == 65.0

    chest = _by_code((await _get_page(client, MUSCLES, demo))["data"])["chest"]
    assert _pick(chest, ("recovery_status", "last_session_id", "model_version")) == {
        "recovery_status": "fatigued", "last_session_id": session_id, "model_version": "recovery-test-1",
    }


async def _session_id_of(db, sql: str, user_id: str) -> str:
    session_id = await db.scalar(text(sql), {"uid": user_id})
    assert session_id is not None, sql
    return session_id


async def _not_found_cases(db) -> list[tuple[str, str]]:
    """(c) buổi completed mới nhất của power, (d) buổi đã xoá mềm của inprogress, (e) UUID không tồn tại."""
    power_latest = await _session_id_of(db, LATEST_COMPLETED_SQL, POWER_ID)
    deleted = await _session_id_of(
        db,
        "SELECT id::text FROM training.workout_sessions WHERE user_id = :uid AND name = 'Buổi nhập nhầm'"
        " AND deleted_at IS NOT NULL",
        INPROGRESS_ID,
    )
    return [("demo", power_latest), ("inprogress", deleted), ("demo", ZERO_UUID)]


@pytest.mark.tc("WRT-20")
async def test_predict_recovery_without_load_wrong_status_or_owner_skips_ai(
    client: AsyncClient, db, auth_headers, fake_ai: _FakeRecoveryAi
):
    before = await _prediction_count(db)
    headers = {"demo": await auth_headers("demo"), "inprogress": await auth_headers("inprogress")}
    empty = await _start(client, headers["demo"], "Trống")
    await _finish(client, headers["demo"], empty)
    res = await _predict_recovery(client, headers["demo"], empty)
    assert res.status_code == 200, res.text
    assert res.json() == {"session_id": empty, "model_version": None, "predictions": []}

    running = await _session_id_of(
        db,
        "SELECT id::text FROM training.workout_sessions WHERE user_id = :uid AND status = 'in_progress'"
        " AND deleted_at IS NULL",
        INPROGRESS_ID,
    )
    _err(await _predict_recovery(client, headers["inprogress"], running), 409, "conflict")
    for persona, session_id in await _not_found_cases(db):
        _err(await _predict_recovery(client, headers[persona], session_id), 404, "workout_session_not_found")
    error = _err(await _predict_recovery(client, headers["demo"], "abc"), 422, "validation_error")
    assert _fields(error) == ["session_id"]
    assert fake_ai.calls == []
    assert await _prediction_count(db) == before


def _assert_ai_unavailable(res: Response, reason: str) -> None:
    """503 service_unavailable, đúng một detail `ai_service` với `code` = reason, không lộ chi tiết kỹ thuật."""
    error = _err(res, 503, "service_unavailable")
    assert len(error["details"]) == 1
    detail = error["details"][0]
    _keys(detail, {"field", "message", "code"})
    assert (detail["field"], detail["code"]) == ("ai_service", reason)
    assert isinstance(detail["message"], str) and detail["message"]
    for shown in (error["message"], detail["message"]):
        for leak in ("RecoveryServiceError", "Exception", "http", get_settings().AI_SERVICE_URL):
            assert leak not in shown, shown


@pytest.mark.tc("WRT-21")
async def test_predict_recovery_ai_failure_returns_503_without_writing(
    client: AsyncClient, db, auth_headers, fake_ai: _FakeRecoveryAi
):
    demo = await auth_headers("demo")
    ids = await _muscle_ids(db)
    session_id, ended_at = await _bench_session(client, db, demo)
    for reason in ("down", "invalid_response"):
        fake_ai.error = recovery_ai_client.RecoveryServiceError(reason)
        _assert_ai_unavailable(await _predict_recovery(client, demo, session_id), reason)
    fake_ai.error = None
    output = _ai_output(ids, ended_at)
    output["predictions"].append(
        {"muscle_group_id": ids["quads"], "fatigue_score": 50.0, "recovered_at": ended_at + timedelta(hours=48)}
    )
    fake_ai.output = output
    _assert_ai_unavailable(await _predict_recovery(client, demo, session_id), "invalid_response")
    assert len(fake_ai.calls) == 3
    assert await _prediction_rows(db, session_id) == {}


async def test_predict_recovery_duplicate_muscle_in_ai_output_returns_503(
    client: AsyncClient, db, auth_headers, fake_ai: _FakeRecoveryAi
):
    demo = await auth_headers("demo")
    ids = await _muscle_ids(db)
    session_id, ended_at = await _bench_session(client, db, demo)
    output = _ai_output(ids, ended_at)
    output["predictions"].append({**output["predictions"][0], "fatigue_score": 10.0})
    fake_ai.output = output
    _assert_ai_unavailable(await _predict_recovery(client, demo, session_id), "invalid_response")
    assert await _prediction_rows(db, session_id) == {}


async def test_predict_recovery_without_token_or_permission_is_rejected(
    client: AsyncClient, db, auth_headers, fake_ai: _FakeRecoveryAi
):
    session_id = await _session_id_of(db, LATEST_COMPLETED_SQL, DEMO_ID)
    res = await client.post(f"{SESSIONS}/{session_id}/predict-recovery")
    _err(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"
    _err(await _predict_recovery(client, await auth_headers("editor"), session_id), 403, "permission_denied")
    assert fake_ai.calls == []
