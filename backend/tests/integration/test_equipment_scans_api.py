"""Integration test /api/v1/ai/equipment-scans (chức năng 7) trên PostgreSQL thật, rollback sau mỗi test."""

import uuid

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.base import encode_cursor

URL = "/api/v1/ai/equipment-scans"
DEMO_ID = "5eed0000-0000-4000-8000-000000000003"

KEYS_SUM = {
    "id", "model_name", "model_version", "latency_ms", "scanned_at",
    "predicted_equipment_id", "predicted_equipment_code", "predicted_equipment_name",
    "confidence", "is_confident", "feedback", "corrected_equipment_id", "resolved_equipment_id",
}


def _assert_error(res: Response, status: int, code: str) -> dict:
    """Kiểm tra body lỗi đúng format chung: một key `error` gồm code, message, details, request_id."""
    assert res.status_code == status, res.text
    body = res.json()
    assert set(body) == {"error"}
    error = body["error"]
    assert set(error) == {"code", "message", "details", "request_id"}
    assert error["code"] == code
    assert isinstance(error["details"], list)
    return error


async def _equipment_id(db: AsyncSession, code: str) -> int:
    equipment_id = await db.scalar(text("SELECT id FROM catalog.equipment WHERE code = :code"), {"code": code})
    assert equipment_id is not None, f"không có thiết bị seed '{code}'"
    return equipment_id


async def _insert_demo_scan(db: AsyncSession) -> tuple[uuid.UUID, int]:
    scan_id = await db.scalar(
        text(
            "INSERT INTO ai.equipment_scans (user_id, model_name, model_version)"
            " VALUES (:uid, 'yolov8_cls_gym', '1.0.0') RETURNING id"
        ),
        {"uid": DEMO_ID},
    )
    cable_id = await _equipment_id(db, "cable_crossover")
    await db.execute(
        text("INSERT INTO ai.equipment_scan_predictions (scan_id, equipment_id, confidence) VALUES (:s, :e, 0.9234)"),
        {"s": scan_id, "e": cable_id},
    )
    return scan_id, cable_id


# --- Thành công ---
async def test_list_scans_own_history_returns_summary_page(client: AsyncClient, db: AsyncSession, auth_headers):
    scan_id, cable_id = await _insert_demo_scan(db)

    res = await client.get(URL, headers=await auth_headers("demo"))

    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == {"data", "pagination"}
    assert body["pagination"] == {"next_cursor": None, "has_more": False}
    # Seed không có lần quét nào của demo (spec EQS-06), nên chỉ còn đúng dòng vừa chèn.
    assert len(body["data"]) == 1
    item = body["data"][0]
    assert set(item) == KEYS_SUM
    # type() thay vì isinstance: bool là lớp con của int, cần phân biệt is_confident với ID.
    json_types = [type(item[k]) for k in ("id", "predicted_equipment_id", "confidence", "is_confident")]
    assert json_types == [str, int, float, bool]
    assert item.pop("scanned_at").endswith("Z")
    assert item == {
        "id": str(scan_id),
        "model_name": "yolov8_cls_gym",
        "model_version": "1.0.0",
        "latency_ms": None,
        "predicted_equipment_id": cable_id,
        "predicted_equipment_code": "cable_crossover",
        "predicted_equipment_name": "Máy kéo cáp đôi",
        "confidence": 0.9234,
        "is_confident": True,
        "feedback": None,
        "corrected_equipment_id": None,
        "resolved_equipment_id": cable_id,
    }


async def test_list_scans_user_without_scans_returns_empty_page(client: AsyncClient, db: AsyncSession, auth_headers):
    await _insert_demo_scan(db)

    res = await client.get(URL, headers=await auth_headers("newbie"))

    assert res.status_code == 200, res.text
    assert res.json() == {"data": [], "pagination": {"next_cursor": None, "has_more": False}}


async def test_list_scans_with_limit_follows_cursor_without_duplicates(
    client: AsyncClient, db: AsyncSession, auth_headers
):
    created = {(await _insert_demo_scan(db))[0] for _ in range(3)}
    h = await auth_headers("demo")

    first = (await client.get(URL, params={"limit": 2}, headers=h)).json()
    next_cursor = first["pagination"]["next_cursor"]
    assert (len(first["data"]), first["pagination"]["has_more"], type(next_cursor)) == (2, True, str)
    second = (await client.get(URL, params={"limit": 2, "cursor": next_cursor}, headers=h)).json()
    assert (len(second["data"]), second["pagination"]) == (1, {"next_cursor": None, "has_more": False})

    items = first["data"] + second["data"]
    assert {uuid.UUID(i["id"]) for i in items} == created
    keys = [(i["scanned_at"], i["id"]) for i in items]
    assert keys == sorted(keys, reverse=True)


# --- Lỗi tham số ---
@pytest.mark.tc("EQS-09")
@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"limit": "0"}, "limit"),
        ({"limit": "101"}, "limit"),
        ({"limit": "abc"}, "limit"),
        ({"cursor": "!!!khong-phai-cursor"}, "cursor"),
        ({"cursor": encode_cursor({"foo": 1})}, "cursor"),
        ({"cursor": encode_cursor({"scanned_at": "abc", "id": "x"})}, "cursor"),
    ],
    ids=["limit-0", "limit-101", "limit-abc", "cursor-garbage", "cursor-missing-keys", "cursor-bad-values"],
)
async def test_list_scans_invalid_query_returns_422(client: AsyncClient, auth_headers, params: dict, field: str):
    res = await client.get(URL, params=params, headers=await auth_headers("demo"))

    error = _assert_error(res, 422, "validation_error")
    assert field in [d["field"] for d in error["details"]]


# --- Auth ---
@pytest.mark.tc("EQS-10")
@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer khong-phai-jwt"}],
    ids=["no-authorization", "malformed-token"],
)
async def test_list_scans_without_valid_token_returns_401(client: AsyncClient, db: AsyncSession, headers: dict):
    count_sql = text("SELECT (SELECT count(*) FROM ai.equipment_scans) + (SELECT count(*) FROM ai.equipment_scan_predictions)")
    before = await db.scalar(count_sql)

    res = await client.get(URL, headers=headers)

    _assert_error(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"
    assert await db.scalar(count_sql) == before


@pytest.mark.tc("EQS-11")
async def test_list_scans_without_ai_use_permission_returns_403(client: AsyncClient, auth_headers):
    res = await client.get(URL, headers=await auth_headers("editor"))

    _assert_error(res, 403, "permission_denied")
