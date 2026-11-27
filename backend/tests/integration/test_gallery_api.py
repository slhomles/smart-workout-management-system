"""Integration test Progress Gallery (chức năng 4) trên PostgreSQL thật, rollback sau mỗi test.

Ảnh luôn lưu vào `tmp_path` qua fixture `local_storage` (không gọi S3 thật).
"""

import hashlib
import io
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient, Response
from PIL import Image
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.schemas.base import encode_cursor
from app.services import gallery_service, storage_service
from app.utils import photo_watermark

URL = "/api/v1/progress-photos"
DEMO_ID = "5eed0000-0000-4000-8000-000000000003"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
KEYS_PHOTO = {
    "id", "angle", "capture_source", "taken_at", "taken_date", "note", "processing_status",
    "original_media_id", "watermarked_media_id", "thumbnail_media_id", "measurement_id", "measured_at",
    "weight_kg", "body_fat_pct", "created_at",
}
UUID_KEYS = ("id", "original_media_id", "watermarked_media_id", "thumbnail_media_id", "measurement_id")
TIME_KEYS = ("taken_at", "measured_at", "created_at")
MEDIA_KEYS = ("original_media_id", "watermarked_media_id", "thumbnail_media_id")
POWER_ID = "5eed0000-0000-4000-8000-000000000004"
SEED_KEYS = {
    "demo-w00": "users/demo/progress/w00-front.jpg",
    "demo-w06": "users/demo/progress/w06-front.jpg",
    "demo-side": "users/demo/progress/w06-side.jpg",
    "demo-w03-deleted": "users/demo/progress/w03-front.jpg",
    "dung-queued": "users/dung/progress/w08-front.jpg",
    "dung-failed": "users/dung/progress/w04-back.heic",
    "dung-w00": "users/dung/progress/w00-front.jpg",
}


@pytest.fixture
def local_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "STORAGE_BACKEND", "local")
    monkeypatch.setattr(get_settings(), "LOCAL_STORAGE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def failing_watermark(local_storage, monkeypatch):
    def _boom(image_bytes: bytes, text: str) -> bytes:
        raise RuntimeError("render hỏng")

    monkeypatch.setattr(photo_watermark, "render_watermark", _boom)
    return local_storage


@pytest.fixture
def failing_storage(local_storage, monkeypatch):
    async def _down(object_key: str, data: bytes, mime_type: str) -> storage_service.StoredObject:
        raise OSError("disk unavailable")

    monkeypatch.setattr(storage_service, "put_object", _down)
    return local_storage


# --- Helper ảnh & request ---
def _encode(image: Image.Image, image_format: str) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def jpeg(width: int, height: int) -> bytes:
    return _encode(Image.new("RGB", (width, height), (40, 120, 200)), "JPEG")


def png(width: int, height: int) -> bytes:
    return _encode(Image.new("RGBA", (width, height), (40, 120, 200, 255)), "PNG")


def gif(width: int, height: int) -> bytes:
    return _encode(Image.new("P", (width, height)), "GIF")


def _parts(fields: dict[str, str], file: tuple[str, bytes, str] | None) -> list:
    """Multipart: field form gửi dạng (None, value) để luôn là multipart/form-data, kể cả khi thiếu file."""
    parts: list = [(name, (None, value)) for name, value in fields.items()]
    return parts + ([("file", file)] if file is not None else [])


async def _upload(client: AsyncClient, headers: dict, fields: dict, file: tuple | None = None) -> Response:
    return await client.post(URL, headers=headers, files=_parts(fields, file))


def _err(res: Response, status: int, code: str) -> dict:
    assert res.status_code == status, res.text
    body = res.json()
    assert set(body) == {"error"} and set(body["error"]) == {"code", "message", "details", "request_id"}
    assert body["error"]["code"] == code and isinstance(body["error"]["details"], list)
    return body["error"]


def _is_uuid(value: object) -> bool:
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value
    except ValueError:
        return False


def _assert_value_types(photo: dict) -> None:
    assert all(_is_uuid(photo[k]) for k in UUID_KEYS if photo[k] is not None)
    assert all(isinstance(photo[k], (int, float)) for k in ("weight_kg", "body_fat_pct") if photo[k] is not None)


def _assert_photo_shape(photo: dict) -> None:
    """Đúng tập KEYS-PHOTO và kiểu JSON theo quy ước chung của spec §5."""
    assert set(photo) == KEYS_PHOTO
    _assert_value_types(photo)
    assert all(photo[k].endswith("Z") for k in TIME_KEYS if photo[k] is not None)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", photo["taken_date"])


def _iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _utc_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# --- Helper đọc DB ---
async def _scalar(db: AsyncSession, sql: str, **params):
    return await db.scalar(text(sql), params)


async def _seed_photo_id(db: AsyncSession, alias: str) -> uuid.UUID:
    return await _scalar(
        db,
        "SELECT p.id FROM media.progress_photos p JOIN media.media_files f ON f.id = p.original_media_id "
        "WHERE f.object_key = :key",
        key=SEED_KEYS[alias],
    )


async def _media(db: AsyncSession, media_id: str) -> dict:
    row = (await db.execute(
        text(
            "SELECT uploaded_by_user_id::text AS uploaded_by_user_id, storage_provider::text AS storage_provider, "
            "bucket, object_key, original_filename, mime_type, size_bytes, checksum_sha256, width_px, height_px, "
            "status::text AS status FROM media.media_files WHERE id = :id"
        ),
        {"id": media_id},
    )).mappings().one()
    return dict(row)


async def _photo_row(db: AsyncSession, photo_id) -> dict:
    row = (await db.execute(
        text(
            "SELECT user_id::text AS user_id, deleted_at IS NULL AS is_live, processing_status::text AS status, "
            "processing_error, watermarked_media_id, thumbnail_media_id, updated_at "
            "FROM media.progress_photos WHERE id = :id"
        ),
        {"id": photo_id},
    )).mappings().one()
    return dict(row)


async def _demo_counts(db: AsyncSession) -> tuple[int, int]:
    photos = await _scalar(db, "SELECT count(*) FROM media.progress_photos WHERE user_id = :u", u=uuid.UUID(DEMO_ID))
    media = await _scalar(
        db, "SELECT count(*) FROM media.media_files WHERE uploaded_by_user_id = :u", u=uuid.UUID(DEMO_ID)
    )
    return photos, media


def _shape(media: dict) -> tuple[str, int, int]:
    return media["mime_type"], media["width_px"], media["height_px"]


async def _media_by_role(db: AsyncSession, photo: dict) -> dict[str, dict]:
    return {key: await _media(db, photo[key]) for key in MEDIA_KEYS}


# --- GAL-01 ---
async def _assert_gal01_body(db: AsyncSession, res: Response) -> dict:
    assert res.status_code == 201, res.text
    photo = res.json()
    assert res.headers["Location"] == f"{URL}/{photo['id']}"
    _assert_photo_shape(photo)
    latest_measurement = await _scalar(
        db,
        "SELECT id::text FROM body.body_measurements WHERE user_id = :u AND measured_at <= now() "
        "ORDER BY measured_at DESC LIMIT 1",
        u=uuid.UUID(DEMO_ID),
    )
    picked = ("angle", "capture_source", "note", "processing_status", "weight_kg", "body_fat_pct", "measurement_id")
    assert {k: photo[k] for k in picked} == {
        "angle": "front", "capture_source": "library", "note": "Tuần 7", "processing_status": "completed",
        "weight_kg": 70.0, "body_fat_pct": 18.4, "measurement_id": latest_measurement,
    }
    db_now = await _scalar(db, "SELECT now()")
    assert abs((_iso(photo["taken_at"]) - db_now).total_seconds()) <= 60
    assert len({photo[k] for k in MEDIA_KEYS}) == 3
    return photo


async def _assert_gal01_db(db: AsyncSession, photo: dict, sent: bytes) -> dict[str, dict]:
    row = await _photo_row(db, photo["id"])
    assert (row["user_id"], row["is_live"]) == (DEMO_ID, True)
    media = await _media_by_role(db, photo)
    bucket = get_settings().AWS_S3_BUCKET
    assert {(m["status"], m["storage_provider"], m["bucket"]) for m in media.values()} == {("available", "s3", bucket)}
    assert all(m["object_key"].startswith(f"users/{DEMO_ID}/progress/") for m in media.values())
    original = media["original_media_id"]
    assert {k: original[k] for k in ("uploaded_by_user_id", "size_bytes", "checksum_sha256", "original_filename")} == {
        "uploaded_by_user_id": DEMO_ID, "size_bytes": len(sent),
        "checksum_sha256": hashlib.sha256(sent).hexdigest(), "original_filename": "a.jpg",
    }
    assert {role: _shape(m) for role, m in media.items()} == {
        "original_media_id": ("image/jpeg", 1200, 1600),
        "watermarked_media_id": ("image/jpeg", 1200, 1600),
        "thumbnail_media_id": ("image/jpeg", 300, 400),
    }
    return media


def _assert_gal01_files(storage: Path, media: dict[str, dict]) -> None:
    paths = {role: storage / m["bucket"] / m["object_key"] for role, m in media.items()}
    assert all(path.is_file() for path in paths.values())
    assert paths["watermarked_media_id"].read_bytes() != paths["original_media_id"].read_bytes()
    with Image.open(paths["thumbnail_media_id"]) as thumbnail:
        assert thumbnail.size == (300, 400)


@pytest.mark.tc("GAL-01")
async def test_upload_valid_jpeg_returns_created_watermarked_photo(client, db, auth_headers, local_storage):
    sent = jpeg(1200, 1600)
    res = await _upload(
        client, await auth_headers("demo"),
        {"angle": "front", "capture_source": "library", "note": "Tuần 7"}, ("a.jpg", sent, "image/jpeg"),
    )
    photo = await _assert_gal01_body(db, res)
    media = await _assert_gal01_db(db, photo, sent)
    _assert_gal01_files(local_storage, media)


# --- GAL-02 ---
async def _demo_first_measured_at(db: AsyncSession) -> datetime:
    return await _scalar(db, "SELECT min(measured_at) FROM body.body_measurements WHERE user_id = :u", u=uuid.UUID(DEMO_ID))


def _assert_completed(res: Response) -> dict:
    assert res.status_code == 201, res.text
    photo = res.json()
    _assert_photo_shape(photo)
    assert photo["processing_status"] == "completed"
    return photo


@pytest.mark.tc("GAL-02")
@pytest.mark.usefixtures("local_storage")
async def test_upload_large_png_after_first_measurement_uses_that_measurement(client, db, auth_headers):
    taken_at = await _demo_first_measured_at(db) + timedelta(hours=1)
    res = await _upload(
        client, await auth_headers("demo"),
        {"angle": "side", "taken_at": _utc_z(taken_at)}, ("big.png", png(3000, 4000), "image/png"),
    )
    photo = _assert_completed(res)
    assert (photo["capture_source"], photo["weight_kg"], photo["body_fat_pct"]) == ("camera", 72.4, 20.0)
    expected_date = await _scalar(db, "SELECT ((:t)::timestamptz AT TIME ZONE 'Asia/Ho_Chi_Minh')::date", t=taken_at)
    assert photo["taken_date"] == expected_date.isoformat()
    media = await _media_by_role(db, photo)
    assert _shape(media["original_media_id"]) == ("image/png", 3000, 4000)
    assert _shape(media["watermarked_media_id"]) == ("image/jpeg", 1536, 2048)
    assert _shape(media["thumbnail_media_id"]) == ("image/jpeg", 300, 400)


@pytest.mark.tc("GAL-02")
@pytest.mark.usefixtures("local_storage")
async def test_upload_taken_before_any_measurement_returns_null_measurement(client, db, auth_headers):
    taken_at = await _demo_first_measured_at(db) - timedelta(days=1)
    res = await _upload(
        client, await auth_headers("demo"),
        {"angle": "back", "taken_at": _utc_z(taken_at)}, ("a.jpg", jpeg(1200, 1600), "image/jpeg"),
    )
    photo = _assert_completed(res)
    measurement = {k: photo[k] for k in ("weight_kg", "body_fat_pct", "measurement_id", "measured_at")}
    assert measurement == dict.fromkeys(measurement)


@pytest.mark.tc("GAL-02")
@pytest.mark.usefixtures("local_storage")
@pytest.mark.parametrize(("persona", "expected"), [("unspecified", (65.0, None)), ("newbie", (None, None))])
async def test_upload_for_persona_without_body_fat_returns_available_measurement(client, auth_headers, persona, expected):
    res = await _upload(client, await auth_headers(persona), {"angle": "front"}, ("a.jpg", jpeg(1200, 1600), "image/jpeg"))
    photo = _assert_completed(res)
    assert (photo["weight_kg"], photo["body_fat_pct"]) == expected


# --- GAL-03 ---
VALID_FILE = ("a.jpg", jpeg(1200, 1600), "image/jpeg")
OVERSIZED = VALID_FILE[1] + b"\0" * (MAX_UPLOAD_BYTES + 1 - len(VALID_FILE[1]))
# Mỗi ca đổi đúng một chỗ so với body hợp lệ: (tên ca, field form, file, field lỗi mong đợi).
INVALID_UPLOADS = [
    ("missing_file", {"angle": "front"}, None, "file"),
    ("not_an_image", {"angle": "front"}, ("x.jpg", b"khong-phai-anh", "image/jpeg"), "file"),
    ("gif", {"angle": "front"}, ("a.gif", gif(10, 10), "image/gif"), "file"),
    ("too_large", {"angle": "front"}, ("a.jpg", OVERSIZED, "image/jpeg"), "file"),
    ("missing_angle", {}, VALID_FILE, "angle"),
    ("unknown_angle", {"angle": "top"}, VALID_FILE, "angle"),
    ("unknown_capture_source", {"angle": "front", "capture_source": "screenshot"}, VALID_FILE, "capture_source"),
    ("future_taken_at", {"angle": "front", "taken_at": "<db_now+1d>"}, VALID_FILE, "taken_at"),
    ("naive_taken_at", {"angle": "front", "taken_at": "2026-01-01T00:00:00"}, VALID_FILE, "taken_at"),
    ("note_too_long", {"angle": "front", "note": "a" * 501}, VALID_FILE, "note"),
]


@pytest.mark.tc("GAL-03")
@pytest.mark.usefixtures("local_storage")
@pytest.mark.parametrize("case", INVALID_UPLOADS, ids=[c[0] for c in INVALID_UPLOADS])
async def test_upload_invalid_input_returns_422_without_side_effects(client, db, auth_headers, case):
    _, fields, file, expected_field = case
    if fields.get("taken_at") == "<db_now+1d>":
        fields = {**fields, "taken_at": _utc_z(await _scalar(db, "SELECT now()") + timedelta(days=1))}
    before = await _demo_counts(db)
    res = await _upload(client, await auth_headers("demo"), fields, file)
    error = _err(res, 422, "validation_error")
    assert expected_field in [d["field"] for d in error["details"]]
    assert await _demo_counts(db) == before
    assert not any(Path(get_settings().LOCAL_STORAGE_DIR).iterdir())


# --- GAL-04 ---
@pytest.mark.tc("GAL-04")
async def test_upload_when_watermark_fails_returns_created_failed_photo(client, db, auth_headers, failing_watermark):
    res = await _upload(client, await auth_headers("demo"), {"angle": "front"}, VALID_FILE)
    assert res.status_code == 201, res.text
    photo = res.json()
    _assert_photo_shape(photo)
    assert (photo["processing_status"], photo["watermarked_media_id"], photo["thumbnail_media_id"]) == ("failed", None, None)
    assert _is_uuid(photo["original_media_id"])
    row = await _photo_row(db, photo["id"])
    assert row["processing_error"] is not None and "RuntimeError" not in row["processing_error"]
    assert (await _media(db, photo["original_media_id"]))["status"] == "available"


@pytest.mark.tc("GAL-04")
async def test_upload_when_storage_down_returns_503_without_rows(client, db, auth_headers, failing_storage):
    before = await _demo_counts(db)
    res = await _upload(client, await auth_headers("demo"), {"angle": "front"}, VALID_FILE)
    error = _err(res, 503, "service_unavailable")
    assert len(error["details"]) == 1 and isinstance(error["details"][0]["message"], str)
    assert error["details"] == [{"field": "storage", "message": error["details"][0]["message"], "code": "down"}]
    assert await _demo_counts(db) == before


# --- GAL-14 ---
@pytest.mark.tc("GAL-14")
@pytest.mark.usefixtures("local_storage")
async def test_process_photo_with_missing_original_marks_failed_without_raising(db):
    photo_id = await _seed_photo_id(db, "dung-queued")
    await gallery_service.process_photo(db, photo_id)
    row = await _photo_row(db, photo_id)
    assert row["status"] == "failed"
    assert row["processing_error"] is not None


@pytest.mark.tc("GAL-14")
async def test_process_photo_requeued_upload_completes_with_generated_media(client, db, auth_headers, local_storage):
    res = await _upload(client, await auth_headers("demo"), {"angle": "front"}, VALID_FILE)
    assert res.status_code == 201, res.text
    photo_id = uuid.UUID(res.json()["id"])
    await db.execute(
        text(
            "UPDATE media.progress_photos SET processing_status = 'queued', watermarked_media_id = NULL, "
            "thumbnail_media_id = NULL WHERE id = :id"
        ),
        {"id": photo_id},
    )
    await gallery_service.process_photo(db, photo_id)
    row = await _photo_row(db, photo_id)
    assert row["status"] == "completed"
    assert row["watermarked_media_id"] is not None and row["thumbnail_media_id"] is not None
    generated = [await _media(db, row[k]) for k in ("watermarked_media_id", "thumbnail_media_id")]
    assert [(m["status"], m["mime_type"]) for m in generated] == [("available", "image/jpeg")] * 2
    assert all((local_storage / m["bucket"] / m["object_key"]).is_file() for m in generated)


@pytest.mark.tc("GAL-14")
@pytest.mark.usefixtures("local_storage")
async def test_process_photo_already_completed_changes_nothing(db):
    photo_id = await _seed_photo_id(db, "demo-w00")
    before = await _photo_row(db, photo_id)
    await gallery_service.process_photo(db, photo_id)
    after = await _photo_row(db, photo_id)
    assert before["status"] == "completed"
    assert after == before


# --- GAL-06..08: GET /progress-photos ---
async def _list(client: AsyncClient, headers: dict, **params) -> dict:
    res = await client.get(URL, headers=headers, params=params)
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == {"data", "pagination"} and set(body["pagination"]) == {"next_cursor", "has_more"}
    for photo in body["data"]:
        _assert_photo_shape(photo)
    return body


async def _seed_ids(db: AsyncSession, *aliases: str) -> list[str]:
    return [str(await _seed_photo_id(db, alias)) for alias in aliases]


async def _assert_taken_dates_match_view(db: AsyncSession, photos: list[dict]) -> None:
    rows = (await db.execute(
        text("SELECT photo_id::text AS id, taken_date FROM media.v_progress_photo_cards WHERE photo_id = ANY(:ids)"),
        {"ids": [uuid.UUID(p["id"]) for p in photos]},
    )).mappings().all()
    expected = {r["id"]: r["taken_date"].isoformat() for r in rows}
    assert {p["id"]: p["taken_date"] for p in photos} == expected


def _pick(photo: dict, *keys: str) -> dict:
    return {k: photo[k] for k in keys}


@pytest.mark.tc("GAL-06")
async def test_list_photos_demo_returns_live_photos_newest_first(client, db, auth_headers):
    body = await _list(client, await auth_headers("demo"))
    assert body["pagination"] == {"next_cursor": None, "has_more": False}
    photos = body["data"]
    side, w06, w00, deleted = await _seed_ids(db, "demo-side", "demo-w06", "demo-w00", "demo-w03-deleted")
    assert [p["id"] for p in photos] == [side, w06, w00]
    assert deleted not in [p["id"] for p in photos]
    assert _pick(photos[0], "angle", "capture_source", "processing_status", "watermarked_media_id",
                 "thumbnail_media_id", "weight_kg", "body_fat_pct", "note") == {
        "angle": "side", "capture_source": "library", "processing_status": "processing",
        "watermarked_media_id": None, "thumbnail_media_id": None, "weight_kg": 70.0, "body_fat_pct": 18.4,
        "note": None,
    }
    assert _pick(photos[2], "processing_status", "weight_kg", "body_fat_pct") == {
        "processing_status": "completed", "weight_kg": 72.4, "body_fat_pct": 20.0,
    }
    assert _is_uuid(photos[2]["watermarked_media_id"]) and _is_uuid(photos[2]["thumbnail_media_id"])
    await _assert_taken_dates_match_view(db, photos)


@pytest.mark.tc("GAL-06")
async def test_list_photos_dung_returns_all_statuses_with_tokyo_dates(client, db, auth_headers):
    body = await _list(client, await auth_headers("dung"))
    photos = body["data"]
    assert [p["id"] for p in photos] == await _seed_ids(db, "dung-queued", "dung-failed", "dung-w00")
    assert [p["processing_status"] for p in photos] == ["queued", "failed", "completed"]
    assert [p["weight_kg"] for p in photos] == [54.0, 53.0, 52.0]
    assert all("processing_error" not in p for p in photos)
    await _assert_taken_dates_match_view(db, photos)


async def _collect_pages(client: AsyncClient, headers: dict, limit: int) -> list[dict]:
    pages, cursor = [], None
    while True:
        params = {"limit": limit} | ({"cursor": cursor} if cursor else {})
        body = await _list(client, headers, **params)
        pages.append(body)
        cursor = body["pagination"]["next_cursor"]
        if not body["pagination"]["has_more"]:
            return pages
        assert cursor is not None and len(pages) < 10


async def _power_live_photo_count(db: AsyncSession) -> int:
    return await _scalar(
        db, "SELECT count(*) FROM media.progress_photos WHERE user_id = :u AND deleted_at IS NULL",
        u=uuid.UUID(POWER_ID),
    )


def _assert_newest_first(photos: list[dict]) -> None:
    taken = [_iso(p["taken_at"]) for p in photos]
    assert taken == sorted(taken, reverse=True)


@pytest.mark.tc("GAL-07")
async def test_list_photos_power_with_limit_follows_cursor_to_end(client, db, auth_headers):
    pages = await _collect_pages(client, await auth_headers("power"), 4)
    shape = [(len(p["data"]), p["pagination"]["has_more"]) for p in pages]
    assert shape == [(4, True), (4, True), (3, False)]
    assert pages[-1]["pagination"]["next_cursor"] is None
    photos = [photo for page in pages for photo in page["data"]]
    ids = {p["id"] for p in photos}
    assert len(ids) == len(photos) == await _power_live_photo_count(db) == 11
    _assert_newest_first(photos)


@pytest.mark.tc("GAL-07")
@pytest.mark.parametrize(("angle", "expected_count"), [("side", 4), ("front", 7)])
async def test_list_photos_power_filtered_by_angle_returns_only_that_angle(client, auth_headers, angle, expected_count):
    body = await _list(client, await auth_headers("power"), angle=angle, limit=100)
    assert len(body["data"]) == expected_count
    assert {p["angle"] for p in body["data"]} == {angle}


INVALID_LIST_PARAMS = [
    ("limit_zero", {"limit": 0}, "limit"),
    ("limit_too_large", {"limit": 101}, "limit"),
    ("garbage_cursor", {"cursor": "!!!khong-phai-cursor"}, "cursor"),
    ("cursor_missing_keys", {"cursor": encode_cursor({"foo": 1})}, "cursor"),
    ("unknown_angle", {"angle": "top"}, "angle"),
]


@pytest.mark.tc("GAL-08")
@pytest.mark.parametrize("case", INVALID_LIST_PARAMS, ids=[c[0] for c in INVALID_LIST_PARAMS])
async def test_list_photos_invalid_params_returns_422(client, auth_headers, case):
    _, params, expected_field = case
    res = await client.get(URL, headers=await auth_headers("demo"), params=params)
    error = _err(res, 422, "validation_error")
    assert [d["field"] for d in error["details"]] == [expected_field]


@pytest.mark.tc("GAL-08")
async def test_list_photos_user_without_photos_returns_empty_page(client, auth_headers):
    body = await _list(client, await auth_headers("newbie"))
    assert body == {"data": [], "pagination": {"next_cursor": None, "has_more": False}}


# --- GAL-09..13: /photo-comparisons ---
COMPARISON_URL = "/api/v1/photo-comparisons"
KEYS_COMPARISON = {"id", "title", "before", "after", "created_at"}
MISSING_PHOTO_ID = "00000000-0000-4000-8000-000000000000"


def _assert_comparison_shape(comparison: dict) -> None:
    assert set(comparison) == KEYS_COMPARISON
    assert _is_uuid(comparison["id"]) and comparison["created_at"].endswith("Z")
    _assert_photo_shape(comparison["before"])
    _assert_photo_shape(comparison["after"])


async def _compare(client: AsyncClient, headers: dict, payload: dict) -> Response:
    return await client.post(COMPARISON_URL, headers=headers, json=payload)


async def _upload_new_photo(client: AsyncClient, headers: dict) -> str:
    res = await _upload(client, headers, {"angle": "front"}, VALID_FILE)
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _comparison_count(db: AsyncSession) -> int:
    return await _scalar(db, "SELECT count(*) FROM media.photo_comparisons")


async def _pair_titles(db: AsyncSession, before_id: str, after_id: str) -> list:
    rows = await db.execute(
        text("SELECT title FROM media.photo_comparisons WHERE before_photo_id = :b AND after_photo_id = :a"),
        {"b": uuid.UUID(before_id), "a": uuid.UUID(after_id)},
    )
    return list(rows.scalars().all())


@pytest.mark.tc("GAL-09")
@pytest.mark.usefixtures("local_storage")
async def test_create_comparison_valid_pair_returns_created_with_embedded_photos(client, db, auth_headers):
    headers = await auth_headers("demo")
    w00, side = await _seed_ids(db, "demo-w00", "demo-side")
    payload = {"before_photo_id": w00, "after_photo_id": side, "title": "Trước/Sau mặt bên"}
    res = await _compare(client, headers, payload)
    assert res.status_code == 201, res.text
    comparison = res.json()
    assert res.headers["Location"] == f"{COMPARISON_URL}/{comparison['id']}"
    _assert_comparison_shape(comparison)
    assert comparison["title"] == "Trước/Sau mặt bên"
    assert _pick(comparison["before"], "id", "weight_kg") == {"id": w00, "weight_kg": 72.4}
    assert _pick(comparison["after"], "id", "weight_kg") == {"id": side, "weight_kg": 70.0}
    assert await _pair_titles(db, w00, side) == ["Trước/Sau mặt bên"]

    new_photo = await _upload_new_photo(client, headers)
    second = await _compare(client, headers, {"before_photo_id": w00, "after_photo_id": new_photo})
    assert second.status_code == 201, second.text
    _assert_comparison_shape(second.json())
    assert second.json()["title"] is None
    assert await _pair_titles(db, w00, new_photo) == [None]


# (tên ca, before, after, title, field lỗi mong đợi). Alias ảnh seed được đổi sang id trong test;
# after/title = None nghĩa là không gửi key đó.
INVALID_COMPARISONS = [
    ("same_photo", "demo-w00", "demo-w00", None, "after_photo_id"),
    ("before_of_other_user", "dung-w00", "demo-w06", None, "before_photo_id"),
    ("after_soft_deleted", "demo-w00", "demo-w03-deleted", None, "after_photo_id"),
    ("before_missing", MISSING_PHOTO_ID, "demo-w06", None, "before_photo_id"),
    ("before_taken_after_after", "demo-w06", "demo-w00", None, "after_photo_id"),
    ("before_not_uuid", "abc", "demo-w06", None, "before_photo_id"),
    ("after_absent", "demo-w00", None, None, "after_photo_id"),
    ("title_too_long", "demo-w00", "demo-side", "x" * 101, "title"),
]


async def _resolve_photo(db: AsyncSession, value: str) -> str:
    return str(await _seed_photo_id(db, value)) if value in SEED_KEYS else value


async def _comparison_payload(db: AsyncSession, before: str, after: str | None, title: str | None) -> dict:
    payload = {"before_photo_id": await _resolve_photo(db, before)}
    if after is not None:
        payload["after_photo_id"] = await _resolve_photo(db, after)
    if title is not None:
        payload["title"] = title
    return payload


@pytest.mark.tc("GAL-10")
@pytest.mark.parametrize("case", INVALID_COMPARISONS, ids=[c[0] for c in INVALID_COMPARISONS])
async def test_create_comparison_invalid_input_returns_422_without_rows(client, db, auth_headers, case):
    _, before, after, title, expected_field = case
    count_before = await _comparison_count(db)
    res = await _compare(client, await auth_headers("demo"), await _comparison_payload(db, before, after, title))
    error = _err(res, 422, "validation_error")
    assert expected_field in [d["field"] for d in error["details"]]
    assert await _comparison_count(db) == count_before


@pytest.mark.tc("GAL-10")
async def test_create_comparison_foreign_and_missing_photo_share_same_message(client, db, auth_headers):
    headers = await auth_headers("demo")
    messages = []
    for before in ("dung-w00", MISSING_PHOTO_ID):
        res = await _compare(client, headers, await _comparison_payload(db, before, "demo-w06", None))
        error = _err(res, 422, "validation_error")
        messages.append((error["message"], [(d["field"], d["message"]) for d in error["details"]]))
    assert messages[0] == messages[1]


@pytest.mark.tc("GAL-11")
async def test_create_comparison_existing_pair_returns_409_and_keeps_seed_row(client, db, auth_headers):
    w00, w06 = await _seed_ids(db, "demo-w00", "demo-w06")
    payload = {"before_photo_id": w00, "after_photo_id": w06, "title": "lặp"}
    res = await _compare(client, await auth_headers("demo"), payload)
    error = _err(res, 409, "conflict")
    assert error["details"] == []
    assert await _pair_titles(db, w00, w06) == ["6 tuần giảm mỡ"]


async def _list_comparisons(client: AsyncClient, headers: dict, **params) -> dict:
    res = await client.get(COMPARISON_URL, headers=headers, params=params)
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == {"data", "pagination"} and set(body["pagination"]) == {"next_cursor", "has_more"}
    for comparison in body["data"]:
        _assert_comparison_shape(comparison)
    return body


@pytest.mark.tc("GAL-12")
async def test_list_comparisons_demo_returns_seed_pair_with_measurements(client, db, auth_headers):
    body = await _list_comparisons(client, await auth_headers("demo"))
    assert body["pagination"] == {"next_cursor": None, "has_more": False}
    assert len(body["data"]) == 1
    comparison = body["data"][0]
    w00, w06 = await _seed_ids(db, "demo-w00", "demo-w06")
    assert comparison["title"] == "6 tuần giảm mỡ"
    assert _pick(comparison["before"], "id", "weight_kg") == {"id": w00, "weight_kg": 72.4}
    assert _pick(comparison["after"], "id", "weight_kg") == {"id": w06, "weight_kg": 70.0}


@pytest.mark.tc("GAL-12")
async def test_list_comparisons_power_returns_front_pair_before_earlier(client, auth_headers):
    body = await _list_comparisons(client, await auth_headers("power"))
    assert [c["title"] for c in body["data"]] == ["6 tháng tăng cơ"]
    comparison = body["data"][0]
    assert _iso(comparison["before"]["taken_at"]) < _iso(comparison["after"]["taken_at"])
    assert comparison["before"]["angle"] == comparison["after"]["angle"] == "front"


@pytest.mark.tc("GAL-12")
async def test_list_comparisons_user_without_pairs_returns_empty_page(client, auth_headers):
    body = await _list_comparisons(client, await auth_headers("newbie"))
    assert body == {"data": [], "pagination": {"next_cursor": None, "has_more": False}}


@pytest.mark.tc("GAL-12")
async def test_list_comparisons_with_soft_deleted_photo_hides_pair(client, db, auth_headers):
    w06 = await _seed_photo_id(db, "demo-w06")
    await db.execute(text("UPDATE media.progress_photos SET deleted_at = now() WHERE id = :id"), {"id": w06})
    body = await _list_comparisons(client, await auth_headers("demo"))
    assert body["data"] == []


async def _collect_comparison_pages(client: AsyncClient, headers: dict, limit: int) -> list[dict]:
    pages, cursor = [], None
    while True:
        params = {"limit": limit} | ({"cursor": cursor} if cursor else {})
        body = await _list_comparisons(client, headers, **params)
        pages.append(body)
        cursor = body["pagination"]["next_cursor"]
        if not body["pagination"]["has_more"]:
            return pages
        assert cursor is not None and len(pages) < 10


async def _create_two_demo_pairs(client: AsyncClient, db: AsyncSession, headers: dict) -> None:
    w00, w06, side = await _seed_ids(db, "demo-w00", "demo-w06", "demo-side")
    new_photo = await _upload_new_photo(client, headers)
    for before, after in ((w00, side), (w06, new_photo)):
        res = await _compare(client, headers, {"before_photo_id": before, "after_photo_id": after})
        assert res.status_code == 201, res.text


async def _demo_seed_pair_id(db: AsyncSession) -> str:
    w00, w06 = await _seed_ids(db, "demo-w00", "demo-w06")
    return await _scalar(
        db, "SELECT id::text FROM media.photo_comparisons WHERE before_photo_id = :b AND after_photo_id = :a",
        b=uuid.UUID(w00), a=uuid.UUID(w06),
    )


def _assert_created_newest_first(comparisons: list[dict]) -> None:
    # Các cặp tạo trong cùng transaction test có thể trùng created_at; id DESC phá hoà nên chỉ yêu cầu không tăng.
    created = [_iso(c["created_at"]) for c in comparisons]
    assert created == sorted(created, reverse=True)


@pytest.mark.tc("GAL-13")
@pytest.mark.usefixtures("local_storage")
async def test_list_comparisons_with_limit_follows_cursor_to_end(client, db, auth_headers):
    headers = await auth_headers("demo")
    await _create_two_demo_pairs(client, db, headers)
    pages = await _collect_comparison_pages(client, headers, 2)
    assert [(len(p["data"]), p["pagination"]["has_more"]) for p in pages] == [(2, True), (1, False)]
    assert pages[-1]["pagination"]["next_cursor"] is None
    comparisons = [c for page in pages for c in page["data"]]
    ids = {c["id"] for c in comparisons}
    assert len(ids) == len(comparisons) == 3
    assert await _demo_seed_pair_id(db) in ids
    _assert_created_newest_first(comparisons)


INVALID_COMPARISON_LIST_PARAMS = [
    ("limit_zero", {"limit": 0}, "limit"),
    ("limit_too_large", {"limit": 101}, "limit"),
    ("garbage_cursor", {"cursor": "!!!khong-phai-cursor"}, "cursor"),
]


@pytest.mark.tc("GAL-13")
@pytest.mark.parametrize("case", INVALID_COMPARISON_LIST_PARAMS, ids=[c[0] for c in INVALID_COMPARISON_LIST_PARAMS])
async def test_list_comparisons_invalid_params_returns_422(client, auth_headers, case):
    _, params, expected_field = case
    res = await client.get(COMPARISON_URL, headers=await auth_headers("demo"), params=params)
    error = _err(res, 422, "validation_error")
    assert [d["field"] for d in error["details"]] == [expected_field]


# --- GAL-15..16: xác thực & phân quyền trên cả 4 endpoint ---
# Mỗi lời gọi dùng body/tham số hợp lệ để lỗi chỉ có thể đến từ token/permission.
async def _call_upload_photo(client: AsyncClient, db: AsyncSession, headers: dict) -> Response:
    return await _upload(client, headers, {"angle": "front"}, VALID_FILE)


async def _call_list_photos(client: AsyncClient, db: AsyncSession, headers: dict) -> Response:
    return await client.get(URL, headers=headers)


async def _call_create_comparison(client: AsyncClient, db: AsyncSession, headers: dict) -> Response:
    return await _compare(client, headers, await _comparison_payload(db, "demo-w00", "demo-side", None))


async def _call_list_comparisons(client: AsyncClient, db: AsyncSession, headers: dict) -> Response:
    return await client.get(COMPARISON_URL, headers=headers)


GUARDED_CALLS = [
    ("upload_photo", _call_upload_photo),
    ("list_photos", _call_list_photos),
    ("create_comparison", _call_create_comparison),
    ("list_comparisons", _call_list_comparisons),
]


async def _gallery_row_counts(db: AsyncSession) -> tuple[int, int, int]:
    """Đếm toàn bảng: lời gọi bị chặn không được tạo dòng nào, của bất kỳ user nào."""
    photos = await _scalar(db, "SELECT count(*) FROM media.progress_photos")
    media = await _scalar(db, "SELECT count(*) FROM media.media_files")
    return photos, media, await _comparison_count(db)


async def _assert_guarded_call_rejected(client: AsyncClient, db: AsyncSession, case: tuple, headers: dict) -> Response:
    """Gọi endpoint, rồi xác nhận không có dòng DB hay file nào được tạo."""
    _, call = case
    before = await _gallery_row_counts(db)
    res = await call(client, db, headers)
    assert await _gallery_row_counts(db) == before
    assert not any(Path(get_settings().LOCAL_STORAGE_DIR).iterdir())
    return res


@pytest.mark.tc("GAL-15")
@pytest.mark.usefixtures("local_storage")
@pytest.mark.parametrize("case", GUARDED_CALLS, ids=[c[0] for c in GUARDED_CALLS])
async def test_gallery_endpoint_without_token_returns_401_without_side_effects(client, db, case):
    res = await _assert_guarded_call_rejected(client, db, case, {})
    _err(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.tc("GAL-16")
@pytest.mark.usefixtures("local_storage")
@pytest.mark.parametrize("case", GUARDED_CALLS, ids=[c[0] for c in GUARDED_CALLS])
async def test_gallery_endpoint_editor_without_permission_returns_403_without_side_effects(
    client, db, auth_headers, case
):
    # content_editor có media:upload nhưng không có progress_photo:manage_own (seeds/01_rbac.sql).
    res = await _assert_guarded_call_rejected(client, db, case, await auth_headers("editor"))
    _err(res, 403, "permission_denied")


ADMIN_LISTS = [("list_photos", _list), ("list_comparisons", _list_comparisons)]


@pytest.mark.tc("GAL-16")
@pytest.mark.parametrize("case", ADMIN_LISTS, ids=[c[0] for c in ADMIN_LISTS])
async def test_gallery_list_admin_with_permission_returns_only_own_empty_data(client, auth_headers, case):
    # Đối chứng: admin có progress_photo:manage_own nhưng không có ảnh, và không thấy ảnh của user khác.
    _, list_endpoint = case
    body = await list_endpoint(client, await auth_headers("admin"))
    assert body["data"] == []
