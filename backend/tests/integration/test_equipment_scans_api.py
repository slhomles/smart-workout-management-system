"""Integration test /api/v1/ai/equipment-scans (chức năng 7) trên PostgreSQL thật, rollback sau mỗi test."""

import io
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

import httpx
import pytest
from httpx import ASGITransport, AsyncClient, Response
from PIL import Image
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.main import app
from app.schemas.base import encode_cursor
from app.services import catalog_service

URL = "/api/v1/ai/equipment-scans"
DEMO_ID = "5eed0000-0000-4000-8000-000000000003"

KEYS_SUM = {
    "id", "model_name", "model_version", "latency_ms", "scanned_at",
    "predicted_equipment_id", "predicted_equipment_code", "predicted_equipment_name",
    "confidence", "is_confident", "feedback", "corrected_equipment_id", "resolved_equipment_id",
}
KEYS_SCAN = KEYS_SUM | {"predictions", "suggested_exercises"}
KEYS_PRED = {"equipment_id", "equipment_code", "equipment_name", "confidence"}
KEYS_SUG = {"exercise_id", "slug", "exercise_name", "difficulty_rank"}
CABLE_SLUGS = {"cable-chest-fly", "face-pull", "cable-triceps-pushdown", "cable-lateral-raise", "cable-crunch"}
CLASSIFY_PATH = "/equipment-recognition/classify"
TOP1_KEYS = ("predicted_equipment_id", "predicted_equipment_code", "predicted_equipment_name", "confidence")


def _image_bytes(image_format: str) -> bytes:
    """Ảnh RGB 32×32 thật sinh bằng Pillow, để backend giải mã được."""
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), (200, 30, 30)).save(buffer, format=image_format)
    return buffer.getvalue()


PNG = _image_bytes("PNG")
JPG = _image_bytes("JPEG")


def _upload(data: bytes = PNG, name: str = "scan.png", content_type: str = "image/png") -> dict[str, Any]:
    """`UP(data, name, type)` của spec: multipart với part file `image`."""
    return {"image": (name, data, content_type)}


def _ai_ok(predictions: list[dict[str, Any]], latency: int | None = 180) -> httpx.Response:
    """`AI_OK(preds, latency)` của spec: phản hồi 200 hợp lệ theo hợp đồng AI service."""
    return httpx.Response(
        200,
        json={"model_name": "yolov8_cls_gym", "model_version": "1.0.0", "latency_ms": latency, "predictions": predictions},
    )


class FakeAi:
    """Thay transport mặc định của httpx: ghi lại request gửi AI service, trả phản hồi do test đặt."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, httpx.Headers, bytes]] = []
        self.reply: httpx.Response | Exception = _ai_ok([])

    async def handle(self, request: httpx.Request) -> httpx.Response:
        body = await request.aread()
        self.calls.append((request.method, str(request.url), request.headers, body))
        if isinstance(self.reply, Exception):
            raise self.reply
        # Mỗi lần gọi một Response mới: Response của httpx chỉ gắn được với một request.
        reply = self.reply
        return httpx.Response(reply.status_code, headers=reply.headers, content=reply.content, request=request)


@pytest.fixture
def fake_ai(monkeypatch: pytest.MonkeyPatch) -> FakeAi:
    """Không test nào gọi mạng thật; client test dùng ASGITransport nên không bị ảnh hưởng."""
    fake = FakeAi()

    async def _handle(_transport: httpx.AsyncHTTPTransport, request: httpx.Request) -> httpx.Response:
        return await fake.handle(request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _handle)
    return fake


@pytest.fixture
def post_scan(client: AsyncClient, auth_headers) -> Callable[..., Awaitable[Response]]:
    """POST một ảnh (mặc định `UP(PNG)`) bằng persona (mặc định demo)."""

    async def _post(files: dict[str, Any] | None = None, persona: str = "demo") -> Response:
        return await client.post(URL, files=files or _upload(), headers=await auth_headers(persona))

    return _post


@pytest.fixture
def catalog_spy(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    """Bọc `catalog_service.list_exercises_for_ai_label`: ghi `(ai_label, limit)` rồi gọi hàm thật."""
    calls: list[tuple[str, int]] = []
    real = catalog_service.list_exercises_for_ai_label

    async def _spy(db: AsyncSession, ai_label: str, limit: int = 20) -> list[Any]:
        calls.append((ai_label, limit))
        return await real(db, ai_label, limit=limit)

    monkeypatch.setattr(catalog_service, "list_exercises_for_ai_label", _spy)
    return calls


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


async def _count_scan_rows(db: AsyncSession) -> tuple[int, int]:
    """Số dòng (`ai.equipment_scans`, `ai.equipment_scan_predictions`), để kiểm tra "không có dòng mới"."""
    row = (
        await db.execute(
            text("SELECT (SELECT count(*) FROM ai.equipment_scans), (SELECT count(*) FROM ai.equipment_scan_predictions)")
        )
    ).one()
    return row[0], row[1]


async def _persisted_scans(db: AsyncSession, scan_id: str) -> list[dict[str, Any]]:
    """Các dòng `ai.equipment_scans` có id này, kèm số dự đoán đã lưu."""
    rows = await db.execute(
        text(
            "SELECT s.user_id::text AS user_id, s.image_media_id, s.latency_ms, s.feedback,"
            " (SELECT count(*) FROM ai.equipment_scan_predictions p WHERE p.scan_id = s.id) AS prediction_count"
            " FROM ai.equipment_scans s WHERE s.id = :id"
        ),
        {"id": scan_id},
    )
    return [dict(r) for r in rows.mappings().all()]


async def _fn_slugs(db: AsyncSession, ai_label: str) -> list[str]:
    """`FN(label)` của spec: slug theo đúng thứ tự `catalog.fn_exercises_for_ai_label`."""
    rows = await db.execute(text("SELECT slug FROM catalog.fn_exercises_for_ai_label(:label)"), {"label": ai_label})
    return list(rows.scalars().all())


def _created_scan(res: Response) -> dict[str, Any]:
    """Kiểm tra 201 + `Location` trỏ đúng lần quét vừa tạo, trả body."""
    assert res.status_code == 201, res.text
    body = res.json()
    assert res.headers["Location"] == f"{URL}/{body['id']}"
    return body


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


# --- POST: quét ảnh ---
async def _assert_cable_summary(db: AsyncSession, body: dict[str, Any]) -> None:
    """Phần KEYS-SUM của EQS-01: top-1 máy kéo cáp đôi đủ tin cậy, kiểu JSON đúng."""
    cable_id = await _equipment_id(db, "cable_crossover")
    assert set(body) == KEYS_SCAN
    # type() thay vì isinstance: bool là lớp con của int, cần phân biệt is_confident với ID.
    typed_keys = ("id", "latency_ms", "predicted_equipment_id", "confidence", "is_confident", "resolved_equipment_id")
    assert [type(body[k]) for k in typed_keys] == [str, int, int, float, bool, int]
    assert body["scanned_at"].endswith("Z")
    scanned_at = datetime.fromisoformat(body["scanned_at"])
    assert abs((scanned_at - await db.scalar(text("SELECT now()"))).total_seconds()) <= 60
    expected = {
        "id": str(uuid.UUID(body["id"])),
        "model_name": "yolov8_cls_gym",
        "model_version": "1.0.0",
        "latency_ms": 180,
        "predicted_equipment_id": cable_id,
        "predicted_equipment_code": "cable_crossover",
        "predicted_equipment_name": "Máy kéo cáp đôi",
        "confidence": 0.9234,
        "is_confident": True,
        "feedback": None,
        "corrected_equipment_id": None,
        "resolved_equipment_id": cable_id,
    }
    assert {k: body[k] for k in expected} == expected


async def _assert_cable_predictions(db: AsyncSession, predictions: list[dict[str, Any]]) -> None:
    """`predictions` của EQS-01: 3 thiết bị theo `confidence` giảm dần, giá trị đọc lại từ DB."""
    codes = ["cable_crossover", "lat_pulldown_machine", "seated_row_machine"]
    expected = [(await _equipment_id(db, c), c, conf) for c, conf in zip(codes, [0.9234, 0.0512, 0.0154])]
    assert [set(p) for p in predictions] == [KEYS_PRED] * 3
    assert [(p["equipment_id"], p["equipment_code"], p["confidence"]) for p in predictions] == expected
    assert [(type(p["equipment_id"]), type(p["confidence"])) for p in predictions] == [(int, float)] * 3
    assert predictions[1]["equipment_name"] == "Máy kéo xô"


async def _assert_suggestions_match_fn(db: AsyncSession, suggestions: list[dict[str, Any]], ai_label: str) -> set[str]:
    """`suggested_exercises` đúng KEYS-SUG, giữ nguyên thứ tự `FN(ai_label)`, độ khó không giảm; trả tập slug."""
    assert [set(s) for s in suggestions] == [KEYS_SUG] * len(suggestions)
    slugs = [s["slug"] for s in suggestions]
    assert slugs == await _fn_slugs(db, ai_label)
    ranks = [s["difficulty_rank"] for s in suggestions]
    assert ranks == sorted(ranks)
    assert {(type(s["exercise_id"]), type(s["difficulty_rank"])) for s in suggestions} <= {(int, int)}
    return set(slugs)


def _assert_single_classify_call(fake_ai: FakeAi, image: bytes) -> None:
    """AI service được gọi đúng một lần: POST multipart tới `/equipment-recognition/classify`, giữ nguyên bytes ảnh."""
    assert len(fake_ai.calls) == 1
    method, url, headers, body = fake_ai.calls[0]
    assert (method, url) == ("POST", get_settings().AI_SERVICE_URL.rstrip("/") + CLASSIFY_PATH)
    assert headers["content-type"].startswith("multipart/form-data")
    assert image in body


@pytest.mark.tc("EQS-01")
async def test_create_scan_confident_cable_machine_returns_201_with_suggestions(
    post_scan, db: AsyncSession, fake_ai: FakeAi
):
    fake_ai.reply = _ai_ok([
        {"label": "cable_crossover_machine", "confidence": 0.9234},
        {"label": "lat_pulldown_machine", "confidence": 0.0512},
        {"label": "seated_cable_row_machine", "confidence": 0.0154},
    ])

    body = _created_scan(await post_scan(_upload(PNG, "scan.png", "image/png")))

    await _assert_cable_summary(db, body)
    await _assert_cable_predictions(db, body["predictions"])
    assert await _assert_suggestions_match_fn(db, body["suggested_exercises"], "cable_crossover_machine") == CABLE_SLUGS
    _assert_single_classify_call(fake_ai, PNG)
    assert await _persisted_scans(db, body["id"]) == [
        {"user_id": DEMO_ID, "image_media_id": None, "latency_ms": 180, "feedback": None, "prediction_count": 3}
    ]


@pytest.mark.tc("EQS-02")
async def test_create_scan_noisy_labels_keeps_top5_mapped_equipment(post_scan, db: AsyncSession, fake_ai: FakeAi):
    raw = [
        (" Dumbbell ", 0.30), ("dumbbell", 0.25), ("khong_co_nhan", 0.99), ("test_retired_machine", 0.98),
        ("barbell", 0.20), ("flat_bench", 0.20), ("kettlebell", 0.10), ("power_rack", 0.04996), ("treadmill", 0.01),
    ]
    fake_ai.reply = _ai_ok([{"label": label, "confidence": conf} for label, conf in raw], latency=None)

    body = _created_scan(await post_scan(_upload(JPG, "scan.jpg", "image/jpeg")))

    # barbell và flat_bench cùng 0.2: đứng theo equipment_id tăng (id đọc qua db, không hardcode).
    tied = sorted([(await _equipment_id(db, code), code) for code in ("barbell", "flat_bench")])
    expected = [("dumbbell", 0.3), *[(code, 0.2) for _, code in tied], ("kettlebell", 0.1), ("power_rack", 0.05)]
    # So cả danh sách: treadmill bị cắt khỏi top-5; khong_co_nhan và test_retired_machine (xoá mềm) bị bỏ.
    assert [(p["equipment_code"], p["confidence"]) for p in body["predictions"]] == expected
    top1_keys = ("predicted_equipment_code", "confidence", "is_confident", "suggested_exercises", "latency_ms")
    assert [body[k] for k in top1_keys] == ["dumbbell", 0.3, False, [], None]
    assert await _persisted_scans(db, body["id"]) == [
        {"user_id": DEMO_ID, "image_media_id": None, "latency_ms": None, "feedback": None, "prediction_count": 5}
    ]


@pytest.mark.tc("EQS-03")
async def test_create_scan_below_confidence_threshold_skips_suggestions(
    post_scan, fake_ai: FakeAi, catalog_spy: list[tuple[str, int]]
):
    fake_ai.reply = _ai_ok([{"label": "cable_crossover_machine", "confidence": 0.5999}])

    body = _created_scan(await post_scan())

    summary = (body["is_confident"], body["predicted_equipment_code"], len(body["predictions"]), body["suggested_exercises"])
    assert summary == (False, "cable_crossover", 1, [])
    assert catalog_spy == []


@pytest.mark.tc("EQS-03")
async def test_create_scan_at_confidence_threshold_suggests_via_catalog_service(
    post_scan, fake_ai: FakeAi, catalog_spy: list[tuple[str, int]]
):
    fake_ai.reply = _ai_ok([{"label": "cable_crossover_machine", "confidence": 0.6}])

    body = _created_scan(await post_scan())

    assert body["is_confident"] is True
    assert {s["slug"] for s in body["suggested_exercises"]} == CABLE_SLUGS
    assert catalog_spy == [("cable_crossover_machine", 20)]


@pytest.mark.tc("EQS-03")
async def test_create_scan_uppercase_label_suggests_by_normalized_label(
    post_scan, db: AsyncSession, fake_ai: FakeAi, catalog_spy: list[tuple[str, int]]
):
    fake_ai.reply = _ai_ok([{"label": "TREADMILL", "confidence": 0.95}])

    body = _created_scan(await post_scan())

    assert body["predicted_equipment_code"] == "treadmill"
    slugs = [s["slug"] for s in body["suggested_exercises"]]
    assert slugs and slugs == await _fn_slugs(db, "treadmill")
    assert catalog_spy == [("treadmill", 20)]


@pytest.mark.tc("EQS-03")
async def test_create_scan_without_predictions_stores_scan_without_top1(
    post_scan, db: AsyncSession, fake_ai: FakeAi, catalog_spy: list[tuple[str, int]]
):
    fake_ai.reply = _ai_ok([])

    body = _created_scan(await post_scan())

    assert [body[k] for k in (*TOP1_KEYS, "resolved_equipment_id")] == [None] * 5
    assert (body["is_confident"], body["predictions"], body["suggested_exercises"]) == (False, [], [])
    assert catalog_spy == []
    assert await _persisted_scans(db, body["id"]) == [
        {"user_id": DEMO_ID, "image_media_id": None, "latency_ms": 180, "feedback": None, "prediction_count": 0}
    ]


@pytest.mark.tc("EQS-12")
async def test_create_scan_failure_after_ai_reply_keeps_no_rows(
    db: AsyncSession, auth_headers, fake_ai: FakeAi, monkeypatch: pytest.MonkeyPatch
):
    fake_ai.reply = _ai_ok([{"label": "cable_crossover_machine", "confidence": 0.9}])

    async def _broken_catalog(*_args: Any, **_kwargs: Any) -> list[Any]:
        raise RuntimeError("boom")

    monkeypatch.setattr(catalog_service, "list_exercises_for_ai_label", _broken_catalog)
    headers = await auth_headers("demo")
    before = await _count_scan_rows(db)
    # Handler 500 nằm ở ServerErrorMiddleware: client mặc định sẽ ném lại exception thay vì trả response.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(URL, files=_upload(), headers=headers)

    error = _assert_error(res, 500, "internal_error")
    assert "boom" not in error["message"]
    # Lỗi xảy ra sau khi AI đã trả kết quả và dữ liệu đã flush: rollback phải xoá hết.
    assert len(fake_ai.calls) == 1
    assert await _count_scan_rows(db) == before
