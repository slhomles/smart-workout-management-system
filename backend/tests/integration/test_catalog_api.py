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
