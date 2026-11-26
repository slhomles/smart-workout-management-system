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
