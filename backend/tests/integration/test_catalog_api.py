"""Integration test module Catalog/Wiki (chức năng 1) trên PostgreSQL thật, rollback sau mỗi test.

ID danh mục là IDENTITY nên không cố định: test đọc ID qua `db` theo `code` (spec exercise-wiki §5).
"""

import uuid
from collections.abc import Iterator

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.base import encode_cursor
from app.services import permission_service

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


# EXW-03(d) `q=test` chờ câu trả lời Q1: seed có bài published "World's Greatest Stretch" khớp "test".


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
