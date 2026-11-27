"""Integration test chức năng 2 (Workout Routine): /workout-plans, /scheduled-workouts, /recovery.

Chạy trên PostgreSQL thật, mỗi test trong transaction rollback (fixture `db` của conftest).
Test case theo spec docs/features/workout-routine.md §5 (mã WRT-xx).
"""

from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text

from app.schemas.base import encode_cursor

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
