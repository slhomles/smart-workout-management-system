"""Integration test module Catalog/Wiki (chức năng 1) trên PostgreSQL thật, rollback sau mỗi test.

ID danh mục là IDENTITY nên không cố định: test đọc ID qua `db` theo `code` (spec exercise-wiki §5).
"""

import json
import uuid
from collections.abc import AsyncGenerator, Iterator

import pytest
import pytest_asyncio
from httpx import AsyncClient, Response
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.schemas.base import encode_cursor
from app.services import catalog_service, permission_service

MUSCLE_GROUPS_URL = "/api/v1/muscle-groups"
EQUIPMENT_URL = "/api/v1/equipment"
MUSCLE_GROUP_KEYS = {
    "id", "code", "name", "name_en", "parent_id", "body_region", "heatmap_region_key",
    "base_recovery_hours", "display_order", "description", "children",
}
EQUIPMENT_KEYS = {"id", "code", "name", "name_en", "description", "category", "image_media_id", "synonyms"}
LAST_PAGE = {"next_cursor": None, "has_more": False}
EXERCISES_URL = "/api/v1/exercises"
EXERCISE_SUMMARY_KEYS = {
    "id", "slug", "name", "name_en", "category", "difficulty_code", "difficulty_name", "difficulty_rank",
    "thumbnail_media_id",
}
HIDDEN_TEST_SLUGS = {"test-draft-exercise", "test-archived-exercise", "test-deleted-exercise"}
LATS_KEYWORD_SLUGS = {
    "dumbbell-row", "barbell-row", "lat-pulldown", "pull-up", "seated-cable-row", "chin-up", "inverted-row",
    "rowing-machine", "medicine-ball-slam", "childs-pose", "ab-wheel-rollout",
}


def _err(res: Response, status: int, code: str) -> dict:
    assert res.status_code == status, res.text
    body = res.json()
    assert set(body) == {"error"} and set(body["error"]) == {"code", "message", "details", "request_id"}
    assert body["error"]["code"] == code
    return body["error"]


def _page(res: Response) -> dict:
    """Body 200 dạng Page[T]: đúng 2 key, nên không thể có success/total/page/offset."""
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == {"data", "pagination"} and set(body["pagination"]) == {"next_cursor", "has_more"}
    return body


async def _catalog_id(db: AsyncSession, table: str, code: str) -> int:
    value = await db.scalar(text(f"SELECT id FROM catalog.{table} WHERE code = :code"), {"code": code})
    assert value is not None, f"không có {table}.code='{code}' trong seed"
    return value


async def _muscle_tree(client: AsyncClient, auth_headers) -> dict:
    return _page(await client.get(MUSCLE_GROUPS_URL, headers=await auth_headers("demo")))


def _walk(nodes: list[dict]) -> Iterator[dict]:
    for node in nodes:
        yield node
        yield from _walk(node["children"])


async def _equipment(client: AsyncClient, auth_headers, params: dict) -> dict:
    return _page(await client.get(EQUIPMENT_URL, params=params, headers=await auth_headers("demo")))


def _by_code(items: list[dict]) -> dict[str, dict]:
    return {item["code"]: item for item in items}


# --- GET /muscle-groups ---
@pytest.mark.tc("EXW-12")
async def test_list_muscle_groups_demo_returns_roots_in_display_order(client: AsyncClient, auth_headers):
    body = await _muscle_tree(client, auth_headers)
    assert body["pagination"] == LAST_PAGE
    assert [node["code"] for node in body["data"]] == ["chest", "back", "shoulders", "arms", "core", "legs"]
    assert all(node["parent_id"] is None and node["body_region"] is not None for node in body["data"])


@pytest.mark.tc("EXW-12")
async def test_list_muscle_groups_roots_have_body_region_object(client: AsyncClient, db: AsyncSession, auth_headers):
    roots = _by_code((await _muscle_tree(client, auth_headers))["data"])
    upper_body_id = await _catalog_id(db, "body_regions", "upper_body")
    assert roots["back"]["body_region"] == {"id": upper_body_id, "code": "upper_body", "name": "Thân trên"}
    assert roots["core"]["body_region"]["code"] == "core"
    assert roots["legs"]["body_region"]["code"] == "lower_body"


@pytest.mark.tc("EXW-12")
async def test_list_muscle_groups_children_follow_display_order(client: AsyncClient, auth_headers):
    roots = _by_code((await _muscle_tree(client, auth_headers))["data"])
    assert [child["code"] for child in roots["back"]["children"]] == ["lats", "traps", "upper_back", "lower_back"]
    assert [child["code"] for child in roots["legs"]["children"]] == [
        "quads", "hamstrings", "glutes", "calves", "adductors",
    ]
    assert roots["chest"]["children"] == []


@pytest.mark.tc("EXW-12")
async def test_list_muscle_groups_tree_covers_every_row_with_exact_keys(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    nodes = list(_walk((await _muscle_tree(client, auth_headers))["data"]))
    row_count = await db.scalar(text("SELECT count(*) FROM catalog.muscle_groups"))
    assert len(nodes) == row_count == 23
    assert len({node["id"] for node in nodes}) == row_count
    assert all(set(node) == MUSCLE_GROUP_KEYS for node in nodes)


@pytest.mark.tc("EXW-12")
async def test_list_muscle_groups_leaf_lats_has_seed_values(client: AsyncClient, db: AsyncSession, auth_headers):
    nodes = _by_code(list(_walk((await _muscle_tree(client, auth_headers))["data"])))
    lats = nodes["lats"]
    assert lats["id"] == await _catalog_id(db, "muscle_groups", "lats")
    assert {key: lats[key] for key in MUSCLE_GROUP_KEYS - {"id", "display_order", "description"}} == {
        "code": "lats",
        "name": "Lưng xô",
        "name_en": "Latissimus Dorsi",
        "parent_id": nodes["back"]["id"],
        "body_region": None,
        "heatmap_region_key": "lats",
        "base_recovery_hours": 60,
        "children": [],
    }


# --- GET /equipment ---
@pytest.mark.tc("EXW-13")
async def test_list_equipment_limit_100_returns_all_active_sorted_by_id(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    body = await _equipment(client, auth_headers, {"limit": 100})
    active_count = await db.scalar(text("SELECT count(*) FROM catalog.equipment WHERE deleted_at IS NULL"))
    ids = [item["id"] for item in body["data"]]
    assert len(ids) == active_count == 27 and body["pagination"] == LAST_PAGE
    assert ids == sorted(set(ids)) and all(isinstance(item_id, int) for item_id in ids)
    assert "test_retired_machine" not in _by_code(body["data"])
    assert all(set(item) == EQUIPMENT_KEYS for item in body["data"])


@pytest.mark.tc("EXW-13")
async def test_list_equipment_dumbbell_has_category_and_synonyms(client: AsyncClient, db: AsyncSession, auth_headers):
    dumbbell = _by_code((await _equipment(client, auth_headers, {"limit": 100}))["data"])["dumbbell"]
    assert dumbbell["id"] == await _catalog_id(db, "equipment", "dumbbell")
    assert (dumbbell["name"], dumbbell["name_en"], dumbbell["synonyms"]) == ("Tạ đơn", "Dumbbell", ["tạ tay"])
    free_weight_id = await _catalog_id(db, "equipment_categories", "free_weight")
    assert dumbbell["category"] == {"id": free_weight_id, "code": "free_weight", "name": "Tạ tự do"}
    assert str(uuid.UUID(dumbbell["image_media_id"])) == dumbbell["image_media_id"]


@pytest.mark.tc("EXW-13")
async def test_list_equipment_cable_crossover_lists_synonyms_without_ai_label(client: AsyncClient, auth_headers):
    cable = _by_code((await _equipment(client, auth_headers, {"limit": 100}))["data"])["cable_crossover"]
    assert cable["synonyms"] == ["máy cáp", "tạ cáp"]
    assert "cable_crossover_machine" not in str(cable)


@pytest.mark.tc("EXW-13")
async def test_list_equipment_default_limit_pages_through_cursor(client: AsyncClient, auth_headers):
    page = await _equipment(client, auth_headers, {})
    assert len(page["data"]) == 20 and page["pagination"]["has_more"] is True
    ids = [item["id"] for item in page["data"]]
    for _ in range(5):  # chặn vòng lặp vô hạn nếu cursor không tiến
        if not page["pagination"]["has_more"]:
            break
        page = await _equipment(client, auth_headers, {"cursor": page["pagination"]["next_cursor"]})
        ids += [item["id"] for item in page["data"]]
    assert page["pagination"] == LAST_PAGE
    assert len(ids) == len(set(ids)) == 27


@pytest.mark.tc("EXW-13")
async def test_list_equipment_filter_cable_category_returns_cable_machines(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    cable_id = await _catalog_id(db, "equipment_categories", "cable")
    body = await _equipment(client, auth_headers, {"category_id": cable_id})
    assert set(_by_code(body["data"])) == {"cable_crossover", "lat_pulldown_machine", "seated_row_machine"}
    assert body["pagination"] == LAST_PAGE


@pytest.mark.tc("EXW-14")
@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"limit": 0}, "limit"),
        ({"limit": 101}, "limit"),
        ({"cursor": "!!!khong-phai-cursor"}, "cursor"),
        ({"category_id": "abc"}, "category_id"),
        ({"category_id": 40000}, "category_id"),
    ],
)
async def test_list_equipment_invalid_query_returns_422(client: AsyncClient, auth_headers, params: dict, field: str):
    res = await client.get(EQUIPMENT_URL, params=params, headers=await auth_headers("demo"))
    err = _err(res, 422, "validation_error")
    assert [detail["field"] for detail in err["details"]] == [field]


@pytest.mark.tc("EXW-14")
async def test_list_equipment_unknown_category_returns_empty_page(client: AsyncClient, auth_headers):
    body = await _equipment(client, auth_headers, {"category_id": 9999})
    assert body == {"data": [], "pagination": LAST_PAGE}


@pytest.mark.parametrize(
    "payload",
    [{"id": True}, {"id": -1}, {"id": "5"}, {"id": 2147483648}, {"offset": 5}],
)
async def test_list_equipment_cursor_with_bad_position_returns_422(client: AsyncClient, auth_headers, payload: dict):
    res = await client.get(EQUIPMENT_URL, params={"cursor": encode_cursor(payload)}, headers=await auth_headers("demo"))
    err = _err(res, 422, "validation_error")
    assert [detail["field"] for detail in err["details"]] == ["cursor"]


# --- Đăng nhập & permission (doc 05 §10) ---
@pytest.mark.parametrize("url", [MUSCLE_GROUPS_URL, EQUIPMENT_URL])
async def test_list_catalog_without_token_returns_401(client: AsyncClient, url: str):
    res = await client.get(url)
    _err(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "case",
    [(MUSCLE_GROUPS_URL, "equipment:read"), (EQUIPMENT_URL, "muscle_group:read")],
)
async def test_list_catalog_without_read_permission_returns_403(
    client: AsyncClient, auth_headers, monkeypatch: pytest.MonkeyPatch, case: tuple[str, str]
):
    url, granted = case

    # Mọi persona seed đều có quyền đọc; giả lập user chỉ có quyền của endpoint kia, không chạm Redis.
    async def _only_granted(_db: AsyncSession, _user_id: uuid.UUID) -> set[str]:
        return {granted}

    headers = await auth_headers("demo")
    monkeypatch.setattr(permission_service, "get_permissions", _only_granted)
    _err(await client.get(url, headers=headers), 403, "permission_denied")


# --- GET /exercises ---
async def _exercises(client: AsyncClient, auth_headers, params: dict) -> dict:
    return _page(await client.get(EXERCISES_URL, params=params, headers=await auth_headers("demo")))


async def _exercise_pages(client: AsyncClient, auth_headers, params: dict) -> list[dict]:
    """Lần theo `next_cursor` tới trang cuối."""
    pages = [await _exercises(client, auth_headers, params)]
    for _ in range(10):  # chặn vòng lặp vô hạn nếu cursor không tiến
        if not pages[-1]["pagination"]["has_more"]:
            break
        next_params = {**params, "cursor": pages[-1]["pagination"]["next_cursor"]}
        pages.append(await _exercises(client, auth_headers, next_params))
    return pages


def _slugs(body: dict) -> list[str]:
    return [item["slug"] for item in body["data"]]


def _is_non_decreasing(values: list[int]) -> bool:
    return all(left <= right for left, right in zip(values, values[1:]))


async def _lats_with_dumbbell_bench(db: AsyncSession) -> dict:
    """Bộ lọc EXW-04 (a): nhóm cơ lưng xô, thiết bị sẵn có tạ đơn + ghế phẳng (lặp param)."""
    return {
        "muscle_group_id": await _catalog_id(db, "muscle_groups", "lats"),
        "available_equipment_id": [
            await _catalog_id(db, "equipment", "dumbbell"),
            await _catalog_id(db, "equipment", "flat_bench"),
        ],
    }


@pytest.mark.tc("EXW-01")
async def test_list_exercises_no_params_returns_first_20_easiest_first(client: AsyncClient, auth_headers):
    body = await _exercises(client, auth_headers, {})
    data = body["data"]
    assert len(data) == 20 and body["pagination"]["has_more"] is True
    assert isinstance(body["pagination"]["next_cursor"], str)
    assert _is_non_decreasing([item["difficulty_rank"] for item in data])
    first = data[0]
    assert (first["difficulty_rank"], first["difficulty_code"], first["difficulty_name"]) == (1, "beginner", "Cơ bản")


@pytest.mark.tc("EXW-01")
async def test_list_exercises_items_have_exact_keys_and_json_types(client: AsyncClient, auth_headers):
    data = (await _exercises(client, auth_headers, {}))["data"]
    assert all(set(item) == EXERCISE_SUMMARY_KEYS for item in data)
    assert all(type(item["id"]) is int for item in data)
    assert all(str(uuid.UUID(item["thumbnail_media_id"])) == item["thumbnail_media_id"] for item in data)


@pytest.mark.tc("EXW-01")
async def test_list_exercises_keeps_search_function_order_with_card_fields(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    data = (await _exercises(client, auth_headers, {}))["data"]
    function_ids = list(await db.scalars(text("SELECT exercise_id FROM catalog.fn_search_exercises(p_limit => 20)")))
    card_rows = await db.execute(
        text("SELECT exercise_id, difficulty_name, thumbnail_media_id FROM catalog.v_exercise_cards")
    )
    cards = {row.exercise_id: (row.difficulty_name, str(row.thumbnail_media_id)) for row in card_rows}
    assert [item["id"] for item in data] == function_ids
    assert [(item["difficulty_name"], item["thumbnail_media_id"]) for item in data] == [
        cards[exercise_id] for exercise_id in function_ids
    ]


@pytest.mark.tc("EXW-02")
async def test_list_exercises_limit_30_pages_until_last_page(client: AsyncClient, auth_headers):
    pages = await _exercise_pages(client, auth_headers, {"limit": 30})
    assert all(len(page["data"]) <= 30 for page in pages)
    assert all(page["pagination"]["has_more"] is True for page in pages[:-1])
    assert pages[-1]["pagination"] == LAST_PAGE


@pytest.mark.tc("EXW-02")
async def test_list_exercises_pages_cover_each_published_exercise_once(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    pages = await _exercise_pages(client, auth_headers, {"limit": 30})
    items = [item for page in pages for item in page["data"]]
    published = await db.scalar(
        text("SELECT count(*) FROM catalog.exercises WHERE status = 'published' AND deleted_at IS NULL")
    )
    assert len(items) == len({item["id"] for item in items}) == published == 71
    assert not HIDDEN_TEST_SLUGS & {item["slug"] for item in items}
    assert _is_non_decreasing([item["difficulty_rank"] for item in items])


@pytest.mark.tc("EXW-03")
async def test_list_exercises_keyword_ignores_accents_and_case(client: AsyncClient, auth_headers):
    plain = await _exercises(client, auth_headers, {"q": "lung xo"})
    accented = await _exercises(client, auth_headers, {"q": "Lưng xô"})
    assert [item["id"] for item in plain["data"]] == [item["id"] for item in accented["data"]]
    assert len(plain["data"]) == 11 and set(_slugs(plain)) == LATS_KEYWORD_SLUGS
    assert plain["data"][0]["difficulty_rank"] == 1
    assert plain["pagination"] == LAST_PAGE


@pytest.mark.tc("EXW-03")
async def test_list_exercises_keyword_matches_equipment_synonym(client: AsyncClient, auth_headers):
    body = await _exercises(client, auth_headers, {"q": "tạ tay", "limit": 100})
    assert {"dumbbell-row", "goblet-squat"} <= set(_slugs(body))


@pytest.mark.tc("EXW-03")
async def test_list_exercises_keyword_matching_only_hidden_exercises_returns_empty(
    client: AsyncClient, auth_headers
):
    # Dùng `[TEST]` thay `test` vì seed `worlds-greatest-stretch` khớp chuỗi con "test" (Q1, phương án A).
    body = await _exercises(client, auth_headers, {"q": "[TEST]"})
    assert body == {"data": [], "pagination": LAST_PAGE}


async def test_list_exercises_blank_keyword_is_ignored(client: AsyncClient, auth_headers):
    blank = await _exercises(client, auth_headers, {"q": "   "})
    unfiltered = await _exercises(client, auth_headers, {})
    assert blank == unfiltered


@pytest.mark.tc("EXW-04")
async def test_list_exercises_filter_lats_with_available_equipment(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    body = await _exercises(client, auth_headers, await _lats_with_dumbbell_bench(db))
    assert set(_slugs(body)) == {"dumbbell-row", "childs-pose"}
    assert body["pagination"] == LAST_PAGE


@pytest.mark.tc("EXW-04")
async def test_list_exercises_filter_primary_only_drops_secondary_lats(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    params = {**await _lats_with_dumbbell_bench(db), "is_primary_only": "true"}
    body = await _exercises(client, auth_headers, params)
    assert _slugs(body) == ["dumbbell-row"]


@pytest.mark.tc("EXW-04")
async def test_list_exercises_filter_parent_muscle_includes_children_up_to_max_rank(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    back_id = await _catalog_id(db, "muscle_groups", "back")
    body = await _exercises(client, auth_headers, {"muscle_group_id": back_id, "max_difficulty_rank": 1, "limit": 100})
    slugs = set(_slugs(body))
    assert {"dumbbell-row", "lat-pulldown", "seated-cable-row"} <= slugs
    assert "barbell-row" not in slugs
    assert body["data"] and all(item["difficulty_rank"] == 1 for item in body["data"])


@pytest.mark.tc("EXW-05")
@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"limit": 0}, "limit"),
        ({"limit": 101}, "limit"),
        ({"cursor": "!!!khong-phai-cursor"}, "cursor"),
        ({"cursor": encode_cursor({"offset": -1})}, "cursor"),
        ({"q": "a" * 101}, "q"),
        ({"max_difficulty_rank": 0}, "max_difficulty_rank"),
        ({"muscle_group_id": "abc"}, "muscle_group_id.0"),
        ({"muscle_group_id": 40000}, "muscle_group_id.0"),
        ({"available_equipment_id": 3000000000}, "available_equipment_id.0"),
    ],
)
async def test_list_exercises_invalid_query_returns_422(client: AsyncClient, auth_headers, params: dict, field: str):
    res = await client.get(EXERCISES_URL, params=params, headers=await auth_headers("demo"))
    err = _err(res, 422, "validation_error")
    assert [detail["field"] for detail in err["details"]] == [field]


@pytest.mark.parametrize("payload", [{"offset": True}, {"offset": "5"}, {"offset": 2147483648}, {"id": 5}])
async def test_list_exercises_cursor_with_bad_offset_returns_422(client: AsyncClient, auth_headers, payload: dict):
    res = await client.get(EXERCISES_URL, params={"cursor": encode_cursor(payload)}, headers=await auth_headers("demo"))
    err = _err(res, 422, "validation_error")
    assert [detail["field"] for detail in err["details"]] == ["cursor"]


async def test_list_exercises_without_token_returns_401(client: AsyncClient):
    res = await client.get(EXERCISES_URL)
    _err(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"


async def test_list_exercises_without_exercise_read_returns_403(
    client: AsyncClient, auth_headers, monkeypatch: pytest.MonkeyPatch
):
    # Mọi persona seed đều có quyền đọc; giả lập user có các quyền đọc catalog khác trừ `exercise:read`.
    async def _without_exercise_read(_db: AsyncSession, _user_id: uuid.UUID) -> set[str]:
        return {"muscle_group:read", "equipment:read", "plan_template:read"}

    headers = await auth_headers("demo")
    monkeypatch.setattr(permission_service, "get_permissions", _without_exercise_read)
    _err(await client.get(EXERCISES_URL, headers=headers), 403, "permission_denied")


# --- GET /exercises/{id_or_slug} ---
EXERCISE_DETAIL_KEYS = {
    "id", "slug", "name", "name_en", "description", "category", "mechanic", "force_type", "is_unilateral",
    "met_value", "supports_ai_tracking", "difficulty", "muscles", "equipment", "instructions", "mistakes", "media",
}
EXERCISE_MUSCLE_KEYS = {"muscle_group_id", "code", "name", "name_en", "role", "activation_ratio"}
EXERCISE_EQUIPMENT_KEYS = {"equipment_id", "code", "name", "name_en", "is_optional"}
EXERCISE_MISTAKE_KEYS = {
    "id", "code", "title", "description", "correction_cue", "at_risk_joint", "is_ai_detectable", "display_order",
}
EXERCISE_MEDIA_KEYS = {
    "media_id", "media_role", "is_primary", "display_order", "caption", "mime_type", "width_px", "height_px",
    "duration_ms",
}
DUMBBELL_ROW_URL = f"{EXERCISES_URL}/dumbbell-row"


async def _exercise_id(db: AsyncSession, slug: str) -> int:
    value = await db.scalar(text("SELECT id FROM catalog.exercises WHERE slug = :slug"), {"slug": slug})
    assert value is not None, f"không có exercises.slug='{slug}' trong seed"
    return value


async def _exercise_detail(client: AsyncClient, auth_headers, id_or_slug: str) -> dict:
    res = await client.get(f"{EXERCISES_URL}/{id_or_slug}", headers=await auth_headers("demo"))
    assert res.status_code == 200, res.text
    return res.json()


async def _assert_exercise_not_found(client: AsyncClient, auth_headers, id_or_slug: str) -> None:
    res = await client.get(f"{EXERCISES_URL}/{id_or_slug}", headers=await auth_headers("demo"))
    assert _err(res, 404, "exercise_not_found")["details"] == []


def _values(items: list[dict], key: str) -> list:
    return [item[key] for item in items]


def _all_have_keys(items: list[dict], keys: set[str]) -> bool:
    return all(set(item) == keys for item in items)


@pytest.mark.tc("EXW-06")
async def test_get_exercise_by_slug_or_id_returns_identical_body(client: AsyncClient, db: AsyncSession, auth_headers):
    by_slug = await _exercise_detail(client, auth_headers, "dumbbell-row")
    exercise_id = await _exercise_id(db, "dumbbell-row")
    by_id = await _exercise_detail(client, auth_headers, str(exercise_id))
    assert by_slug == by_id
    assert set(by_slug) == EXERCISE_DETAIL_KEYS
    assert type(by_slug["id"]) is int and by_slug["id"] == exercise_id and by_slug["slug"] == "dumbbell-row"


@pytest.mark.tc("EXW-06")
async def test_get_exercise_dumbbell_row_has_seed_general_info(client: AsyncClient, db: AsyncSession, auth_headers):
    detail = await _exercise_detail(client, auth_headers, "dumbbell-row")
    assert (detail["name"], detail["name_en"]) == ("Chèo tạ đơn một tay", "One-Arm Dumbbell Row")
    assert (detail["category"], detail["mechanic"], detail["force_type"]) == ("strength", "compound", "pull")
    assert detail["is_unilateral"] is True and detail["supports_ai_tracking"] is True
    assert type(detail["met_value"]) is float and detail["met_value"] == 4.5
    beginner_id = await _catalog_id(db, "difficulty_levels", "beginner")
    assert detail["difficulty"] == {"id": beginner_id, "code": "beginner", "name": "Cơ bản", "rank": 1}


@pytest.mark.tc("EXW-06")
async def test_get_exercise_dumbbell_row_lists_muscles_with_role_and_ratio(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    muscles = (await _exercise_detail(client, auth_headers, "dumbbell-row"))["muscles"]
    assert len(muscles) == 4 and set(_values(muscles, "code")) == {"lats", "upper_back", "rear_delts", "biceps"}
    assert _all_have_keys(muscles, EXERCISE_MUSCLE_KEYS)
    assert {type(ratio) for ratio in _values(muscles, "activation_ratio")} == {float}
    lats = muscles[0]
    assert (lats["code"], lats["role"], lats["activation_ratio"]) == ("lats", "primary", 1.0)
    assert lats["muscle_group_id"] == await _catalog_id(db, "muscle_groups", "lats")


@pytest.mark.tc("EXW-06")
async def test_get_exercise_dumbbell_row_lists_required_equipment_and_steps(client: AsyncClient, auth_headers):
    detail = await _exercise_detail(client, auth_headers, "dumbbell-row")
    equipment, instructions = detail["equipment"], detail["instructions"]
    assert set(_values(equipment, "code")) == {"dumbbell", "flat_bench"}
    assert _all_have_keys(equipment, EXERCISE_EQUIPMENT_KEYS)
    assert _values(equipment, "is_optional") == [False, False]
    assert _all_have_keys(instructions, {"step_no", "content"})
    assert _values(instructions, "step_no") == [1, 2, 3]
    assert instructions[0]["content"].startswith("Tì gối")


@pytest.mark.tc("EXW-06")
async def test_get_exercise_dumbbell_row_lists_ai_detectable_mistakes(client: AsyncClient, auth_headers):
    mistakes = (await _exercise_detail(client, auth_headers, "dumbbell-row"))["mistakes"]
    assert _values(mistakes, "code") == ["DB_ROW_TORSO_ROTATION", "DB_ROW_ROUNDED_BACK"]
    assert _all_have_keys(mistakes, EXERCISE_MISTAKE_KEYS)
    assert _values(mistakes, "at_risk_joint") == ["spine", "spine"]
    assert _values(mistakes, "is_ai_detectable") == [True, True]


@pytest.mark.tc("EXW-06")
async def test_get_exercise_dumbbell_row_has_one_primary_thumbnail_and_gif(client: AsyncClient, auth_headers):
    media = (await _exercise_detail(client, auth_headers, "dumbbell-row"))["media"]
    for role in ("thumbnail", "gif"):
        items = [item for item in media if item["media_role"] == role]
        assert _values(items, "is_primary") == [True]
    assert _all_have_keys(media, EXERCISE_MEDIA_KEYS)
    assert all(str(uuid.UUID(media_id)) == media_id for media_id in _values(media, "media_id"))


@pytest.mark.tc("EXW-07")
async def test_get_exercise_back_squat_orders_muscles_and_mistakes(client: AsyncClient, auth_headers):
    detail = await _exercise_detail(client, auth_headers, "barbell-back-squat")
    assert _values(detail["muscles"], "code") == ["quads", "glutes", "hamstrings", "lower_back", "abs"]
    assert _values(detail["mistakes"], "code") == [
        "SQUAT_BACK_ROUNDING", "SQUAT_KNEE_VALGUS", "SQUAT_HEEL_LIFT", "SQUAT_SHALLOW_DEPTH",
    ]
    assert detail["mistakes"][-1]["at_risk_joint"] is None


@pytest.mark.tc("EXW-07")
async def test_get_exercise_back_squat_orders_media_by_display_order(client: AsyncClient, auth_headers):
    media = (await _exercise_detail(client, auth_headers, "barbell-back-squat"))["media"]
    assert _all_have_keys(media, EXERCISE_MEDIA_KEYS)
    assert _values(media, "display_order") == [0, 1, 2, 3, 4, 5]
    assert _values(media, "media_role") == ["thumbnail", "gif", "video", "image", "image", "image"]
    images = media[3:]
    assert _values(images, "is_primary") == [False, False, False]
    assert _values(images, "caption") == ["Tư thế bắt đầu", "Điểm thấp nhất", "Đứng lên hoàn thành"]


@pytest.mark.tc("EXW-07")
async def test_get_exercise_back_squat_video_has_mime_type_and_duration(client: AsyncClient, auth_headers):
    media = (await _exercise_detail(client, auth_headers, "barbell-back-squat"))["media"]
    videos = [item for item in media if item["media_role"] == "video"]
    assert len(videos) == 1 and videos[0]["mime_type"] == "video/mp4"
    assert type(videos[0]["duration_ms"]) is int and videos[0]["duration_ms"] > 0


@pytest.mark.tc("EXW-07")
async def test_get_exercise_bench_press_lists_optional_equipment_last(client: AsyncClient, auth_headers):
    equipment = (await _exercise_detail(client, auth_headers, "barbell-bench-press"))["equipment"]
    assert [item["is_optional"] for item in equipment] == [False, False, True]
    assert equipment[-1]["code"] == "power_rack"


@pytest.mark.tc("EXW-08")
@pytest.mark.parametrize(
    "id_or_slug",
    [
        "test-draft-exercise", "test-archived-exercise", "test-deleted-exercise", "khong-ton-tai",
        "999999", "99999999999",
    ],
)
async def test_get_exercise_hidden_or_unknown_returns_404(client: AsyncClient, auth_headers, id_or_slug: str):
    await _assert_exercise_not_found(client, auth_headers, id_or_slug)


@pytest.mark.tc("EXW-08")
async def test_get_exercise_draft_by_id_returns_404(client: AsyncClient, db: AsyncSession, auth_headers):
    draft_id = await _exercise_id(db, "test-draft-exercise")
    await _assert_exercise_not_found(client, auth_headers, str(draft_id))


# Ngoài các ca của EXW-08: chuỗi không thể là id/slug hợp lệ vẫn phải 404, không để DB hay int() báo lỗi thành 500.
@pytest.mark.parametrize(
    "id_or_slug", ["Dumbbell-Row", "abc%00", pytest.param("9" * 5000, id="5000-digits"), "0"]
)
async def test_get_exercise_malformed_identifier_returns_404(client: AsyncClient, auth_headers, id_or_slug: str):
    await _assert_exercise_not_found(client, auth_headers, id_or_slug)


async def test_get_exercise_without_token_returns_401(client: AsyncClient):
    res = await client.get(DUMBBELL_ROW_URL)
    _err(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"


async def test_get_exercise_without_exercise_read_returns_403(
    client: AsyncClient, auth_headers, monkeypatch: pytest.MonkeyPatch
):
    # Mọi persona seed đều có quyền đọc; giả lập user có các quyền đọc catalog khác trừ `exercise:read`.
    async def _without_exercise_read(_db: AsyncSession, _user_id: uuid.UUID) -> set[str]:
        return {"muscle_group:read", "equipment:read", "plan_template:read"}

    headers = await auth_headers("demo")
    monkeypatch.setattr(permission_service, "get_permissions", _without_exercise_read)
    _err(await client.get(DUMBBELL_ROW_URL, headers=headers), 403, "permission_denied")


# --- GET /exercises/{id_or_slug}/alternatives ---
ALTERNATIVES_URL = f"{DUMBBELL_ROW_URL}/alternatives"
ALTERNATIVE_KEYS = {"id", "slug", "name", "difficulty_rank", "is_curated", "muscle_overlap", "score"}
DUMBBELL_ROW_ALTERNATIVE_SLUGS = [
    "barbell-row", "seated-cable-row", "lat-pulldown", "chin-up", "pull-up", "inverted-row",
    "medicine-ball-slam", "rowing-machine", "childs-pose", "ab-wheel-rollout",
]


async def _alternatives(client: AsyncClient, auth_headers, params: dict) -> dict:
    return _page(await client.get(ALTERNATIVES_URL, params=params, headers=await auth_headers("demo")))


async def _alternative_pages(client: AsyncClient, auth_headers, params: dict) -> list[dict]:
    """Lần theo `next_cursor` tới trang cuối."""
    pages = [await _alternatives(client, auth_headers, params)]
    for _ in range(10):  # chặn vòng lặp vô hạn nếu cursor không tiến
        if not pages[-1]["pagination"]["has_more"]:
            break
        next_params = {**params, "cursor": pages[-1]["pagination"]["next_cursor"]}
        pages.append(await _alternatives(client, auth_headers, next_params))
    return pages


@pytest.mark.tc("EXW-09")
async def test_list_alternatives_dumbbell_row_returns_single_page_by_score(client: AsyncClient, auth_headers):
    body = await _alternatives(client, auth_headers, {})
    assert len(body["data"]) == 10 and body["pagination"] == LAST_PAGE
    assert _slugs(body)[:5] == ["barbell-row", "seated-cable-row", "lat-pulldown", "chin-up", "pull-up"]
    assert "dumbbell-row" not in _slugs(body)
    scores = _values(body["data"], "score")
    assert all(left >= right for left, right in zip(scores, scores[1:]))


@pytest.mark.tc("EXW-09")
async def test_list_alternatives_items_have_exact_keys_and_json_types(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    data = (await _alternatives(client, auth_headers, {}))["data"]
    assert _all_have_keys(data, ALTERNATIVE_KEYS)
    typed_keys = ("id", "difficulty_rank", "is_curated", "muscle_overlap", "score")
    json_types = {tuple(type(item[key]) for key in typed_keys) for item in data}
    assert json_types == {(int, int, bool, float, float)}
    assert data[0]["id"] == await _exercise_id(db, "barbell-row")


@pytest.mark.tc("EXW-09")
async def test_list_alternatives_curated_alternatives_come_first(client: AsyncClient, auth_headers):
    data = (await _alternatives(client, auth_headers, {}))["data"]
    first = data[0]
    assert (first["is_curated"], first["muscle_overlap"], first["score"]) == (True, 1.0, 1.55)
    assert [item["is_curated"] for item in data[:3]] == [True, True, False]


@pytest.mark.tc("EXW-10")
async def test_list_alternatives_busy_barbell_drops_barbell_row(client: AsyncClient, db: AsyncSession, auth_headers):
    barbell_id = await _catalog_id(db, "equipment", "barbell")
    data = (await _alternatives(client, auth_headers, {"unavailable_equipment_id": barbell_id}))["data"]
    assert len(data) == 9 and "barbell-row" not in _values(data, "slug")
    assert (data[0]["slug"], data[0]["is_curated"]) == ("seated-cable-row", True)


@pytest.mark.tc("EXW-10")
async def test_list_alternatives_many_busy_machines_keep_remaining_order(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    busy_codes = ["barbell", "seated_row_machine", "lat_pulldown_machine", "pull_up_bar"]
    busy_ids = [await _catalog_id(db, "equipment", code) for code in busy_codes]
    body = await _alternatives(client, auth_headers, {"unavailable_equipment_id": busy_ids})
    assert _slugs(body) == ["inverted-row", "medicine-ball-slam", "rowing-machine", "childs-pose", "ab-wheel-rollout"]


@pytest.mark.tc("EXW-10")
async def test_list_alternatives_limit_3_pages_through_cursor(client: AsyncClient, auth_headers):
    pages = await _alternative_pages(client, auth_headers, {"limit": 3})
    assert _slugs(pages[0]) == ["barbell-row", "seated-cable-row", "lat-pulldown"]
    assert pages[0]["pagination"]["has_more"] is True
    assert _slugs(pages[1]) == ["chin-up", "pull-up", "inverted-row"]
    slugs = [slug for page in pages for slug in _slugs(page)]
    assert slugs == DUMBBELL_ROW_ALTERNATIVE_SLUGS and len(set(slugs)) == 10
    assert pages[-1]["pagination"] == LAST_PAGE


@pytest.mark.tc("EXW-11")
@pytest.mark.parametrize("id_or_slug", ["test-draft-exercise", "khong-ton-tai"])
async def test_list_alternatives_hidden_or_unknown_exercise_returns_404(
    client: AsyncClient, auth_headers, id_or_slug: str
):
    res = await client.get(f"{EXERCISES_URL}/{id_or_slug}/alternatives", headers=await auth_headers("demo"))
    assert _err(res, 404, "exercise_not_found")["details"] == []


@pytest.mark.tc("EXW-11")
@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"limit": 0}, "limit"),
        ({"unavailable_equipment_id": "abc"}, "unavailable_equipment_id.0"),
        ({"cursor": "!!!khong-phai-cursor"}, "cursor"),
    ],
)
async def test_list_alternatives_invalid_query_returns_422(
    client: AsyncClient, auth_headers, params: dict, field: str
):
    res = await client.get(ALTERNATIVES_URL, params=params, headers=await auth_headers("demo"))
    err = _err(res, 422, "validation_error")
    assert [detail["field"] for detail in err["details"]] == [field]


# `p_limit` của hàm SQL là `integer`: offset tối đa cộng thêm `limit + 1` không được tràn kiểu thành 500.
async def test_list_alternatives_max_offset_cursor_returns_empty_last_page(client: AsyncClient, auth_headers):
    body = await _alternatives(client, auth_headers, {"cursor": encode_cursor({"offset": 2147483647})})
    assert body == {"data": [], "pagination": LAST_PAGE}


async def test_list_alternatives_without_token_returns_401(client: AsyncClient):
    res = await client.get(ALTERNATIVES_URL)
    _err(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"


async def test_list_alternatives_without_exercise_read_returns_403(
    client: AsyncClient, auth_headers, monkeypatch: pytest.MonkeyPatch
):
    # Mọi persona seed đều có quyền đọc; giả lập user có các quyền đọc catalog khác trừ `exercise:read`.
    async def _without_exercise_read(_db: AsyncSession, _user_id: uuid.UUID) -> set[str]:
        return {"muscle_group:read", "equipment:read", "plan_template:read"}

    headers = await auth_headers("demo")
    monkeypatch.setattr(permission_service, "get_permissions", _without_exercise_read)
    _err(await client.get(ALTERNATIVES_URL, headers=headers), 403, "permission_denied")


# --- catalog_service.list_exercises_for_ai_label (chức năng 7 gọi qua service, không có route) ---
AI_LABEL_EXERCISE_FIELDS = {"equipment_id", "equipment_name", "exercise_id", "slug", "exercise_name", "difficulty_rank"}
CABLE_CROSSOVER_SLUGS = {"cable-chest-fly", "face-pull", "cable-triceps-pushdown", "cable-lateral-raise", "cable-crunch"}


async def _exercises_for_ai_label(db: AsyncSession, ai_label: str) -> list[dict]:
    return [item.model_dump() for item in await catalog_service.list_exercises_for_ai_label(db, ai_label)]


@pytest.mark.tc("EXW-17")
async def test_list_exercises_for_ai_label_cable_machine_returns_cable_exercises(db: AsyncSession):
    items = await _exercises_for_ai_label(db, "cable_crossover_machine")
    assert {item["slug"] for item in items} == CABLE_CROSSOVER_SLUGS
    assert _all_have_keys(items, AI_LABEL_EXERCISE_FIELDS)
    cable_crossover_id = await _catalog_id(db, "equipment", "cable_crossover")
    assert all(item["equipment_id"] == cable_crossover_id for item in items)
    assert all(type(item["exercise_id"]) is int for item in items)
    assert _is_non_decreasing(_values(items, "difficulty_rank"))


@pytest.mark.tc("EXW-17")
async def test_list_exercises_for_ai_label_padded_uppercase_label_matches_same_result(db: AsyncSession):
    normalized = await _exercises_for_ai_label(db, "cable_crossover_machine")
    padded = await _exercises_for_ai_label(db, "  CABLE_CROSSOVER_MACHINE ")
    assert padded and padded == normalized


@pytest.mark.tc("EXW-17")
@pytest.mark.parametrize("ai_label", ["test_retired_machine", "khong_co_nhan"])
async def test_list_exercises_for_ai_label_retired_or_unknown_label_returns_empty(db: AsyncSession, ai_label: str):
    assert await catalog_service.list_exercises_for_ai_label(db, ai_label) == []


# --- GET /plan-templates ---
PLAN_TEMPLATES_URL = "/api/v1/plan-templates"
PLAN_TEMPLATE_KEYS = {
    "id", "name", "description", "goal_type_id", "difficulty", "duration_weeks", "day_count", "created_at",
}


def _plan_id(nn: int) -> str:
    return f"5eed1000-0000-4000-8000-{nn:012d}"


ACTIVE_TEMPLATE_IDS = {_plan_id(nn) for nn in range(1, 7)}


async def _plan_templates(client: AsyncClient, auth_headers, params: dict) -> dict:
    return _page(await client.get(PLAN_TEMPLATES_URL, params=params, headers=await auth_headers("demo")))


async def _goal_type_id(db: AsyncSession, code: str) -> int:
    value = await db.scalar(text("SELECT id FROM body.fitness_goal_types WHERE code = :code"), {"code": code})
    assert value is not None, f"không có fitness_goal_types.code='{code}' trong seed"
    return value


def _ids(body: dict) -> list[str]:
    return [item["id"] for item in body["data"]]


@pytest.mark.tc("EXW-15")
async def test_list_plan_templates_no_params_returns_only_active_templates(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    body = await _plan_templates(client, auth_headers, {})
    ids = _ids(body)
    assert body["pagination"] == LAST_PAGE
    assert len(ids) == len(set(ids)) and set(ids) == ACTIVE_TEMPLATE_IDS
    personal_ids = {
        str(plan_id)
        for plan_id in await db.scalars(text("SELECT id FROM training.workout_plans WHERE owner_user_id IS NOT NULL"))
    }
    assert not personal_ids & set(ids)
    assert not {_plan_id(7), _plan_id(8)} & set(ids)


@pytest.mark.tc("EXW-15")
async def test_list_plan_templates_items_have_exact_keys_and_utc_created_at(client: AsyncClient, auth_headers):
    data = (await _plan_templates(client, auth_headers, {}))["data"]
    assert _all_have_keys(data, PLAN_TEMPLATE_KEYS)
    assert all(str(uuid.UUID(item["id"])) == item["id"] for item in data)
    assert all(item["created_at"].endswith("Z") for item in data)
    assert all(type(item["day_count"]) is int for item in data)


@pytest.mark.tc("EXW-15")
async def test_list_plan_templates_ppl_and_upper_lower_have_seed_values(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    templates = {item["id"]: item for item in (await _plan_templates(client, auth_headers, {}))["data"]}
    ppl = templates[_plan_id(2)]
    intermediate_id = await _catalog_id(db, "difficulty_levels", "intermediate")
    assert (ppl["name"], ppl["goal_type_id"]) == ("Push / Pull / Legs", await _goal_type_id(db, "gain_muscle"))
    assert ppl["difficulty"] == {"id": intermediate_id, "code": "intermediate", "name": "Trung cấp", "rank": 2}
    assert (ppl["duration_weeks"], ppl["day_count"]) == (12, 3)
    assert templates[_plan_id(3)]["day_count"] == 4


@pytest.mark.tc("EXW-15")
async def test_list_plan_templates_limit_4_pages_through_cursor(client: AsyncClient, auth_headers):
    first = await _plan_templates(client, auth_headers, {"limit": 4})
    assert len(first["data"]) == 4 and first["pagination"]["has_more"] is True
    second = await _plan_templates(client, auth_headers, {"limit": 4, "cursor": first["pagination"]["next_cursor"]})
    assert len(second["data"]) == 2 and second["pagination"] == LAST_PAGE
    ids = _ids(first) + _ids(second)
    assert len(ids) == len(set(ids)) and set(ids) == ACTIVE_TEMPLATE_IDS


@pytest.mark.tc("EXW-15")
async def test_list_plan_templates_filters_by_goal_and_difficulty(client: AsyncClient, db: AsyncSession, auth_headers):
    by_goal = await _plan_templates(client, auth_headers, {"goal_type_id": await _goal_type_id(db, "gain_muscle")})
    assert set(_ids(by_goal)) == {_plan_id(2), _plan_id(3)}
    beginner_id = await _catalog_id(db, "difficulty_levels", "beginner")
    by_difficulty = await _plan_templates(client, auth_headers, {"difficulty_level_id": beginner_id})
    assert set(_ids(by_difficulty)) == {_plan_id(1), _plan_id(5), _plan_id(6)}
    unknown_goal = await _plan_templates(client, auth_headers, {"goal_type_id": 9999})
    assert unknown_goal == {"data": [], "pagination": LAST_PAGE}


@pytest.mark.tc("EXW-16")
@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"limit": 0}, "limit"),
        ({"limit": 101}, "limit"),
        ({"cursor": "!!!khong-phai-cursor"}, "cursor"),
        ({"goal_type_id": "abc"}, "goal_type_id"),
        ({"difficulty_level_id": 40000}, "difficulty_level_id"),
    ],
)
async def test_list_plan_templates_invalid_query_returns_422(
    client: AsyncClient, auth_headers, params: dict, field: str
):
    res = await client.get(PLAN_TEMPLATES_URL, params=params, headers=await auth_headers("demo"))
    err = _err(res, 422, "validation_error")
    assert [detail["field"] for detail in err["details"]] == [field]


@pytest.mark.parametrize("payload", [{"created_at": "khong-phai-ngay", "id": _plan_id(1)}, {"id": _plan_id(1)}])
async def test_list_plan_templates_cursor_with_bad_position_returns_422(
    client: AsyncClient, auth_headers, payload: dict
):
    res = await client.get(
        PLAN_TEMPLATES_URL, params={"cursor": encode_cursor(payload)}, headers=await auth_headers("demo")
    )
    err = _err(res, 422, "validation_error")
    assert [detail["field"] for detail in err["details"]] == ["cursor"]


# --- Đăng nhập & permission của cả 6 endpoint (EXW-18, EXW-19) ---
MODULE_URLS = [EXERCISES_URL, DUMBBELL_ROW_URL, ALTERNATIVES_URL, MUSCLE_GROUPS_URL, EQUIPMENT_URL, PLAN_TEMPLATES_URL]
EXERCISE_READ_URLS = {EXERCISES_URL, DUMBBELL_ROW_URL, ALTERNATIVES_URL}
NEWBIE_ID = uuid.UUID("5eed0000-0000-4000-8000-000000000008")


@pytest.mark.tc("EXW-18")
@pytest.mark.parametrize("url", MODULE_URLS)
async def test_module_endpoint_without_token_returns_401(client: AsyncClient, url: str):
    res = await client.get(url)
    _err(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"


@pytest_asyncio.fixture
async def newbie_permission_cache() -> AsyncGenerator[tuple[Redis, str], None]:
    """Key cache quyền `perm:…08`; luôn xoá ở teardown, nếu không newbie bị 403 ở test khác suốt TTL 5 phút."""
    redis = get_redis()
    key = permission_service.cache_key(NEWBIE_ID)
    await redis.delete(key)
    try:
        yield redis, key
    finally:
        await redis.delete(key)


async def _assert_cache_cleared(redis: Redis, key: str) -> None:
    await redis.delete(key)
    assert await redis.exists(key) == 0


@pytest.mark.tc("EXW-19")
async def test_module_endpoints_user_without_roles_returns_403(
    client: AsyncClient, db: AsyncSession, auth_headers, newbie_permission_cache: tuple[Redis, str]
):
    redis, key = newbie_permission_cache
    headers = await auth_headers("newbie")
    # Mọi persona seed đều có quyền đọc: thu hồi role trong transaction của test (rollback ở teardown của `db`).
    await db.execute(text("DELETE FROM auth.user_roles WHERE user_id = :user_id"), {"user_id": NEWBIE_ID})
    for url in MODULE_URLS:
        _err(await client.get(url, headers=headers), 403, "permission_denied")
    assert json.loads(await redis.get(key)) == []
    await _assert_cache_cleared(redis, key)


@pytest.mark.tc("EXW-19")
async def test_module_endpoints_cached_exercise_read_only_allows_exercises(
    client: AsyncClient, auth_headers, newbie_permission_cache: tuple[Redis, str]
):
    redis, key = newbie_permission_cache
    headers = await auth_headers("newbie")
    await redis.set(key, json.dumps(["exercise:read"]), ex=300)
    for url in MODULE_URLS:
        res = await client.get(url, headers=headers)
        if url in EXERCISE_READ_URLS:
            assert res.status_code == 200, (url, res.text)
        else:
            _err(res, 403, "permission_denied")
    await _assert_cache_cleared(redis, key)


@pytest.mark.tc("EXW-19")
@pytest.mark.parametrize("persona", ["editor", "admin"])
async def test_module_endpoints_editor_and_admin_return_200(client: AsyncClient, auth_headers, persona: str):
    headers = await auth_headers(persona)
    for url in MODULE_URLS:
        res = await client.get(url, headers=headers)
        assert res.status_code == 200, (url, res.text)
