"""Integration test phát media (spec be-media-delivery) trên PostgreSQL thật, rollback sau mỗi test.

Mọi test HTTP chạy với `local_storage` (file trong `tmp_path`) hoặc `s3_fake` (client S3 giả): không gọi AWS thật.
"""

import hashlib
import io
import json
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from botocore.exceptions import NoCredentialsError
from httpx import AsyncClient, Response
from PIL import Image
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis_client import get_redis
from app.main import app
from app.services import permission_service, storage_service

URL = "/api/v1/media"
METADATA_PATH = "/api/v1/media/{media_id}"
CONTENT_PATH = "/api/v1/media/{media_id}/content"
DB_BUCKET = "smart-workout-media"
MISSING_ID = uuid.UUID("00000000-0000-4000-8000-000000000000")
EDITOR_ID = uuid.UUID("5eed0000-0000-4000-8000-000000000002")
NEWBIE_ID = uuid.UUID("5eed0000-0000-4000-8000-000000000008")
# Media tạo thêm cho MED-06 (a): GIF của bài nháp, không có trong seed.
DRAFT_GIF_KEY = "catalog/exercises/test-draft-exercise/demo.gif"
SEED_KEYS = {
    "gif-row": "catalog/exercises/dumbbell-row/demo.gif",
    "thumb-row": "catalog/exercises/dumbbell-row/thumbnail.jpg",
    "video-squat": "catalog/exercises/barbell-back-squat/tutorial.mp4",
    "img-dumbbell": "catalog/equipment/dumbbell.jpg",
    "demo-w00": "users/demo/progress/w00-front.jpg",
    "demo-w00-wm": "users/demo/progress/w00-front.wm.jpg",
    "demo-w00-thumb": "users/demo/progress/w00-front.thumb.jpg",
    "demo-avatar": "users/5eed0000-0000-4000-8000-000000000003/avatar.jpg",
    "demo-stale": "users/demo/uploads/tmp-stale.jpg",
    "dung-w00": "users/dung/progress/w00-front.jpg",
    "dung-w00-wm": "users/dung/progress/w00-front.wm.jpg",
    "demo-avatar-old": "users/demo/avatar-old.jpg",
    "khoa-broken": "users/khoa/uploads/broken.jpg",
    "plateau-side": "users/plateau/progress/side.jpg",
}
KEYS_MEDIA = {
    "id", "mime_type", "size_bytes", "width_px", "height_px", "duration_ms", "url", "url_expires_at", "created_at",
}
FORBIDDEN_KEYS = {
    "bucket", "object_key", "storage_provider", "checksum_sha256", "uploaded_by_user_id", "original_filename",
    "status", "deleted_at",
}
SIZE_KEYS = ("size_bytes", "width_px", "height_px", "duration_ms")
TIME_KEYS = ("url_expires_at", "created_at")
# Client S3 giả trả URL theo key để chứng minh bucket/key lấy từ bản ghi DB.
FAKE_SIGNED_URL = "https://s3.test/{key}?X-Amz-Signature=fake"


# --- Fixture ---
@pytest.fixture
def local_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "STORAGE_BACKEND", "local")
    monkeypatch.setattr(get_settings(), "LOCAL_STORAGE_DIR", str(tmp_path))
    return tmp_path


class FakeS3Client:
    """Client S3 giả: ghi lại lời gọi `generate_presigned_url`, trả URL giả hoặc ném `error`; không gọi mạng."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.error = error

    # Tên tham số theo đúng chữ ký của boto3 (ClientMethod, Params, ExpiresIn) để nhận cả lời gọi dạng keyword.
    def generate_presigned_url(
        self, ClientMethod: str, Params: dict[str, str] | None = None, ExpiresIn: int = 3600, **kw: Any
    ) -> str:
        self.calls.append({"ClientMethod": ClientMethod, "Params": Params, "ExpiresIn": ExpiresIn})
        if self.error is not None:
            raise self.error
        assert Params is not None
        return FAKE_SIGNED_URL.format(key=Params["Key"])


@dataclass
class S3Fake:
    """Điều khiển client S3 giả mà `storage_service._s3_client()` trả về trong test."""

    client: FakeS3Client = field(default_factory=FakeS3Client)

    def renew(self, error: Exception | None = None) -> FakeS3Client:
        """Thay bằng client giả mới (ném `error` khi ký nếu có)."""
        self.client = FakeS3Client(error)
        return self.client


@pytest.fixture
def s3_fake(monkeypatch) -> S3Fake:
    settings = get_settings()
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    # Bucket cấu hình khác bucket trong DB: URL phải ký theo bucket của bản ghi media.
    monkeypatch.setattr(settings, "AWS_S3_BUCKET", "bucket-khac")
    fake = S3Fake()
    monkeypatch.setattr(storage_service, "_s3_client", lambda: fake.client)
    return fake


@pytest.fixture
def read_object_spy(monkeypatch) -> list[tuple[str, str]]:
    """Bọc `storage_service.read_object` (vẫn gọi hàm gốc) để đếm số lần đọc kho."""
    calls: list[tuple[str, str]] = []
    original = storage_service.read_object

    async def _spy(bucket: str, object_key: str) -> bytes | None:
        calls.append((bucket, object_key))
        return await original(bucket, object_key)

    monkeypatch.setattr(storage_service, "read_object", _spy)
    return calls


@dataclass
class MediaApi:
    """Gọi `/media` thay persona seed và tra id media seed qua `db` (cùng transaction rollback của test)."""

    client: AsyncClient
    db: AsyncSession
    auth_headers: Callable[[str], Awaitable[dict[str, str]]]

    async def media_id(self, alias: str) -> uuid.UUID:
        """Id của media seed theo tên gọi tắt ở spec §5; `missing` là UUID không tồn tại."""
        if alias == "missing":
            return MISSING_ID
        media_id = await self.db.scalar(
            text("SELECT id FROM media.media_files WHERE object_key = :key"), {"key": SEED_KEYS[alias]}
        )
        assert media_id is not None, f"không có media seed '{alias}'"
        return media_id

    async def row(self, media_id: uuid.UUID) -> dict[str, Any]:
        """Các cột của bản ghi media dùng để đối chiếu với response."""
        sql = text("SELECT size_bytes, duration_ms, created_at FROM media.media_files WHERE id = :id")
        return dict((await self.db.execute(sql, {"id": media_id})).mappings().one())

    async def get(self, persona: str, media_id: uuid.UUID) -> Response:
        """`GET /media/{media_id}` với token của persona."""
        return await self.client.get(f"{URL}/{media_id}", headers=await self.auth_headers(persona))

    async def content(self, persona: str, media_id: uuid.UUID) -> Response:
        """`GET /media/{media_id}/content` với token của persona."""
        return await self.client.get(f"{URL}/{media_id}/content", headers=await self.auth_headers(persona))


@pytest.fixture
def media_api(client: AsyncClient, db: AsyncSession, auth_headers) -> MediaApi:
    return MediaApi(client, db, auth_headers)


@pytest_asyncio.fixture
async def newbie_perm_cache() -> AsyncGenerator[tuple[Redis, str], None]:
    """Key cache quyền `perm:…08`, xoá trước và sau test (không FLUSHDB), theo tiền lệ EXW-19.

    Xoá trước: test khác gọi bằng newbie đã cache đủ quyền (TTL 5 phút), làm MED-14 không thấy role bị thu hồi.
    Xoá sau: nếu còn key giả, newbie bị sai quyền ở test khác suốt TTL.
    """
    redis = get_redis()
    key = permission_service.cache_key(NEWBIE_ID)
    await redis.delete(key)
    try:
        yield redis, key
    finally:
        await redis.delete(key)


# --- Helper kiểm tra ---
def _local_url(media_id: uuid.UUID) -> str:
    return f"{URL}/{media_id}/content"


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _is_uuid(value: object) -> bool:
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value
    except ValueError:
        return False


def _is_int(value: object) -> bool:
    # bool là lớp con của int trong Python nhưng là kiểu JSON khác: không được tính là số nguyên.
    return isinstance(value, int) and not isinstance(value, bool)


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _assert_media_shape(media: dict[str, Any]) -> None:
    """Đúng KEYS-MEDIA và kiểu JSON theo quy ước chung của spec §5."""
    assert set(media) == KEYS_MEDIA
    assert not FORBIDDEN_KEYS & set(media)
    assert _is_uuid(media["id"])
    assert all(media[k] is None or _is_int(media[k]) for k in SIZE_KEYS)
    assert all(media[k].endswith("Z") for k in TIME_KEYS if media[k] is not None)


def _ok(res: Response) -> dict[str, Any]:
    assert res.status_code == 200, res.text
    media = res.json()
    _assert_media_shape(media)
    return media


def _err(res: Response, status: int, code: str) -> dict:
    assert res.status_code == status, res.text
    body = res.json()
    assert set(body) == {"error"} and set(body["error"]) == {"code", "message", "details", "request_id"}
    assert body["error"]["code"] == code and isinstance(body["error"]["details"], list)
    return body["error"]


def _write_object(storage_dir: Path, alias: str, data: bytes) -> None:
    """Đặt file của media seed vào kho local, đúng vị trí `<LOCAL_STORAGE_DIR>/<bucket>/<object_key>`."""
    path = storage_dir / DB_BUCKET / SEED_KEYS[alias]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _jpeg(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (40, 120, 200)).save(buffer, format="JPEG")
    return buffer.getvalue()


async def _missing_error(media_api: MediaApi) -> dict:
    """Body 404 của media không tồn tại: mốc để so mọi 404 phát sinh ở bước phân quyền (spec §6 ý 2)."""
    return _err(await media_api.get("demo", MISSING_ID), 404, "not_found")


def _assert_same_as_missing(res: Response, missing: dict) -> None:
    """404 không phân biệt được với ca không tồn tại: cùng code, cùng message, `details` rỗng."""
    err = _err(res, 404, "not_found")
    assert err["details"] == []
    assert err["message"] == missing["message"]


async def _is_available(db: AsyncSession, media_id: uuid.UUID) -> bool:
    sql = text("SELECT status = 'available' AND deleted_at IS NULL FROM media.media_files WHERE id = :id")
    return bool(await db.scalar(sql, {"id": media_id}))


async def _is_uploaded_by(db: AsyncSession, media_id: uuid.UUID, persona: str) -> bool:
    sql = text(
        "SELECT EXISTS (SELECT 1 FROM media.media_files m JOIN auth.users u ON u.id = m.uploaded_by_user_id"
        " WHERE m.id = :id AND u.email = :email)"
    )
    return bool(await db.scalar(sql, {"id": media_id, "email": f"{persona}@smartworkout.local"}))


async def _insert_draft_exercise_gif(db: AsyncSession) -> uuid.UUID:
    """GIF chính của bài nháp `test-draft-exercise`, editor tải lên, đúng dữ liệu MED-06 (a); rollback cuối test."""
    media_id = await db.scalar(
        text(
            "INSERT INTO media.media_files (uploaded_by_user_id, storage_provider, bucket, object_key, mime_type,"
            " size_bytes, checksum_sha256, status)"
            " VALUES (:uploader, 's3', :bucket, :key, 'image/gif', 1000, :checksum, 'available') RETURNING id"
        ),
        {
            "uploader": EDITOR_ID,
            "bucket": DB_BUCKET,
            "key": DRAFT_GIF_KEY,
            "checksum": hashlib.sha256(DRAFT_GIF_KEY.encode()).hexdigest(),
        },
    )
    exercise_id = await db.scalar(text("SELECT id FROM catalog.exercises WHERE slug = 'test-draft-exercise'"))
    await db.execute(
        text(
            "INSERT INTO catalog.exercise_media (exercise_id, media_id, media_role, is_primary, display_order)"
            " VALUES (:exercise_id, :media_id, 'gif', true, 1)"
        ),
        {"exercise_id": exercise_id, "media_id": media_id},
    )
    return media_id


async def _assert_cache_cleared(redis: Redis, key: str) -> None:
    """MED-14: sau test Redis không còn `perm:…08` (tiền lệ EXW-19); fixture vẫn xoá lại ở teardown."""
    await redis.delete(key)
    assert await redis.exists(key) == 0


# --- GET /media/{media_id}: local ---
@pytest.mark.tc("MED-01")
@pytest.mark.usefixtures("local_storage")
async def test_get_media_catalog_gif_local_returns_metadata_without_reading_storage(
    media_api: MediaApi, read_object_spy: list[tuple[str, str]]
):
    gif_id = await media_api.media_id("gif-row")

    media = _ok(await media_api.get("demo", gif_id))

    row = await media_api.row(gif_id)
    assert media["id"] == str(gif_id)
    assert (media["mime_type"], media["width_px"], media["height_px"]) == ("image/gif", 480, 360)
    assert (media["size_bytes"], media["duration_ms"]) == (row["size_bytes"], row["duration_ms"])
    assert _is_positive_int(media["duration_ms"])
    assert _parse_time(media["created_at"]) == row["created_at"]
    assert (media["url"], media["url_expires_at"]) == (_local_url(gif_id), None)
    assert read_object_spy == []


@dataclass(frozen=True)
class CatalogCase:
    """Một ca MED-02: persona gọi media danh mục và các field phải khớp chính xác."""

    persona: str
    alias: str
    expected: dict[str, Any] = field(default_factory=dict)
    has_positive_duration: bool = False


CATALOG_CASES = [
    pytest.param(
        CatalogCase("power", "video-squat", {"mime_type": "video/mp4", "width_px": 1280, "height_px": 720}, True),
        id="a-power-video",
    ),
    pytest.param(
        CatalogCase(
            "dung", "thumb-row", {"mime_type": "image/jpeg", "width_px": 400, "height_px": 300, "duration_ms": None}
        ),
        id="b-dung-thumbnail",
    ),
    pytest.param(
        CatalogCase("newbie", "img-dumbbell", {"mime_type": "image/jpeg", "width_px": 800, "height_px": 600}),
        id="c-newbie-equipment",
    ),
    pytest.param(CatalogCase("editor", "gif-row"), id="d-editor-gif"),
    pytest.param(CatalogCase("admin", "gif-row"), id="d-admin-gif"),
]


@pytest.mark.tc("MED-02")
@pytest.mark.usefixtures("local_storage")
@pytest.mark.parametrize("case", CATALOG_CASES)
async def test_get_media_catalog_media_any_role_returns_200(media_api: MediaApi, case: CatalogCase):
    media_id = await media_api.media_id(case.alias)

    media = _ok(await media_api.get(case.persona, media_id))

    assert media["id"] == str(media_id)
    assert media["url"] == _local_url(media_id)
    assert {k: media[k] for k in case.expected} == case.expected
    if case.has_positive_duration:
        assert _is_positive_int(media["duration_ms"])


# (persona, media, (width_px, height_px), size_bytes) theo bảng MED-03.
OWN_MEDIA_CASES = [
    pytest.param(("demo", "demo-w00", (3024, 4032), 2350000), id="demo-original"),
    pytest.param(("demo", "demo-w00-wm", (1512, 2016), 980000), id="demo-watermarked"),
    pytest.param(("demo", "demo-w00-thumb", (300, 400), 42000), id="demo-thumbnail"),
    pytest.param(("demo", "demo-avatar", (512, 512), 85000), id="demo-avatar"),
    pytest.param(("dung", "dung-w00-wm", (1512, 2016), 900000), id="dung-watermarked"),
]


@pytest.mark.tc("MED-03")
@pytest.mark.usefixtures("local_storage")
@pytest.mark.parametrize("case", OWN_MEDIA_CASES)
async def test_get_media_own_media_returns_200(media_api: MediaApi, case: tuple[str, str, tuple[int, int], int]):
    persona, alias, size_px, size_bytes = case
    media_id = await media_api.media_id(alias)

    media = _ok(await media_api.get(persona, media_id))

    assert media["id"] == str(media_id)
    assert media["url"] == _local_url(media_id)
    assert (media["mime_type"], media["duration_ms"]) == ("image/jpeg", None)
    assert ((media["width_px"], media["height_px"]), media["size_bytes"]) == (size_px, size_bytes)


# (persona, media) theo bảng MED-04; `missing` cũng nằm trong danh sách để cả 7 ca được so cùng một mốc.
NOT_OWNER_CASES = [
    ("demo", "dung-w00"),
    ("demo", "dung-w00-wm"),
    ("demo", "plateau-side"),
    ("power", "demo-w00-thumb"),
    ("editor", "demo-w00"),
    ("dung", "demo-avatar"),
    ("demo", "missing"),
]


@pytest.mark.tc("MED-04")
@pytest.mark.usefixtures("local_storage")
@pytest.mark.parametrize(("persona", "alias"), NOT_OWNER_CASES, ids=[f"{p}-{a}" for p, a in NOT_OWNER_CASES])
async def test_get_media_not_owner_returns_404_same_as_missing(media_api: MediaApi, persona: str, alias: str):
    media_id = await media_api.media_id(alias)
    missing = await _missing_error(media_api)
    if alias != "missing":
        # Media có thật và đang available: 404 chỉ có thể do không phải chủ, vẫn không lộ là media tồn tại.
        assert await _is_available(media_api.db, media_id)

    res = await media_api.get(persona, media_id)

    _assert_same_as_missing(res, missing)


# (persona, media) MED-05 (a)–(c): chính người tải lên gọi media seed chưa sẵn sàng hoặc đã xoá mềm.
NOT_READY_CASES = [
    pytest.param("demo", "demo-stale", id="a-pending-upload"),
    pytest.param("inprogress", "khoa-broken", id="b-failed"),
    pytest.param("demo", "demo-avatar-old", id="c-soft-deleted"),
]


@pytest.mark.tc("MED-05")
@pytest.mark.usefixtures("local_storage")
@pytest.mark.parametrize(("persona", "alias"), NOT_READY_CASES)
async def test_get_media_own_media_not_available_returns_404_same_as_missing(
    media_api: MediaApi, persona: str, alias: str
):
    media_id = await media_api.media_id(alias)
    missing = await _missing_error(media_api)
    # Người gọi là chủ sở hữu: 404 chỉ có thể đến từ trạng thái/xoá mềm (bước 1 trước bước sở hữu).
    assert await _is_uploaded_by(media_api.db, media_id, persona)

    res = await media_api.get(persona, media_id)

    _assert_same_as_missing(res, missing)


# (persona, media) MED-05 (d), (e): media đang xem được bị chuyển sang `quarantined`.
QUARANTINE_CASES = [
    pytest.param("demo", "demo-avatar", id="d-own-avatar"),
    pytest.param("power", "gif-row", id="e-catalog-gif"),
]


@pytest.mark.tc("MED-05")
@pytest.mark.usefixtures("local_storage")
@pytest.mark.parametrize(("persona", "alias"), QUARANTINE_CASES)
async def test_get_media_quarantined_returns_404_same_as_missing(media_api: MediaApi, persona: str, alias: str):
    media_id = await media_api.media_id(alias)
    missing = await _missing_error(media_api)
    # Trước khi chặn vẫn xem được, nên 404 sau đó chỉ do trạng thái `quarantined`.
    _ok(await media_api.get(persona, media_id))
    await media_api.db.execute(
        text("UPDATE media.media_files SET status = 'quarantined' WHERE id = :id"), {"id": media_id}
    )

    res = await media_api.get(persona, media_id)

    _assert_same_as_missing(res, missing)


# Thứ tự request trong 2 test MED-06 là có chủ đích: request lỗi làm session `db` rollback về savepoint
# (`_override` trong conftest), xoá luôn dữ liệu test vừa ghi. Vì vậy lấy mốc `missing` trước khi ghi,
# và gọi ca 404 (demo) sau cùng.
@pytest.mark.tc("MED-06")
@pytest.mark.usefixtures("local_storage")
async def test_get_media_draft_exercise_gif_returns_404_except_uploader(media_api: MediaApi):
    missing = await _missing_error(media_api)
    media_id = await _insert_draft_exercise_gif(media_api.db)

    editor_media = _ok(await media_api.get("editor", media_id))
    demo_res = await media_api.get("demo", media_id)

    assert editor_media["id"] == str(media_id)
    assert (editor_media["mime_type"], editor_media["size_bytes"]) == ("image/gif", 1000)
    assert editor_media["url"] == _local_url(media_id)
    _assert_same_as_missing(demo_res, missing)


@pytest.mark.tc("MED-06")
@pytest.mark.usefixtures("local_storage")
async def test_get_media_soft_deleted_equipment_image_returns_404_except_uploader(media_api: MediaApi):
    media_id = await media_api.media_id("img-dumbbell")
    missing = await _missing_error(media_api)
    await media_api.db.execute(text("UPDATE catalog.equipment SET deleted_at = now() WHERE code = 'dumbbell'"))

    editor_media = _ok(await media_api.get("editor", media_id))
    demo_res = await media_api.get("demo", media_id)

    assert editor_media["id"] == str(media_id)
    assert editor_media["url"] == _local_url(media_id)
    _assert_same_as_missing(demo_res, missing)


@pytest.mark.tc("MED-07")
@pytest.mark.usefixtures("local_storage")
@pytest.mark.parametrize(
    "path", [f"{URL}/abc", f"{URL}/123", f"{URL}/abc/content"], ids=["metadata-abc", "metadata-123", "content-abc"]
)
async def test_get_media_invalid_media_id_returns_422(media_api: MediaApi, path: str):
    res = await media_api.client.get(path, headers=await media_api.auth_headers("demo"))

    err = _err(res, 422, "validation_error")
    assert any("media_id" in (detail["field"] or "") for detail in err["details"])


# --- GET /media/{media_id}: S3 presigned URL ---
@pytest.mark.tc("MED-08")
async def test_get_media_s3_catalog_gif_returns_presigned_url(media_api: MediaApi, s3_fake: S3Fake):
    gif_id = await media_api.media_id("gif-row")

    t0 = datetime.now(timezone.utc)
    res = await media_api.get("demo", gif_id)
    t1 = datetime.now(timezone.utc)

    media = _ok(res)
    assert media["url"] == FAKE_SIGNED_URL.format(key=SEED_KEYS["gif-row"])
    assert s3_fake.client.calls == [
        {"ClientMethod": "get_object", "Params": {"Bucket": DB_BUCKET, "Key": SEED_KEYS["gif-row"]}, "ExpiresIn": 900}
    ]
    assert media["url_expires_at"].endswith("Z")
    assert t0 + timedelta(seconds=899) <= _parse_time(media["url_expires_at"]) <= t1 + timedelta(seconds=901)
    assert (media["mime_type"], media["width_px"], media["height_px"]) == ("image/gif", 480, 360)


@pytest.mark.tc("MED-08")
async def test_get_media_s3_own_watermarked_photo_returns_presigned_url(media_api: MediaApi, s3_fake: S3Fake):
    fake_client = s3_fake.renew()
    media_id = await media_api.media_id("demo-w00-wm")

    media = _ok(await media_api.get("demo", media_id))

    assert media["url"] == FAKE_SIGNED_URL.format(key=SEED_KEYS["demo-w00-wm"])
    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["Params"]["Key"] == SEED_KEYS["demo-w00-wm"]
    assert media["url_expires_at"] is not None


@pytest.mark.tc("MED-09")
@pytest.mark.parametrize("alias", ["dung-w00", "demo-stale", "missing"])
async def test_get_media_s3_denied_media_returns_404_without_signing(media_api: MediaApi, s3_fake: S3Fake, alias: str):
    media_id = await media_api.media_id(alias)

    _err(await media_api.get("demo", media_id), 404, "not_found")

    assert s3_fake.client.calls == []


@pytest.mark.tc("MED-09")
async def test_get_media_s3_signing_fails_returns_503_without_leaking_error(media_api: MediaApi, s3_fake: S3Fake):
    s3_fake.renew(error=NoCredentialsError())
    gif_id = await media_api.media_id("gif-row")

    err = _err(await media_api.get("demo", gif_id), 503, "service_unavailable")

    assert len(err["details"]) == 1
    detail = err["details"][0]
    assert set(detail) == {"field", "message", "code"}
    assert (detail["field"], detail["code"]) == ("storage", "down")
    assert isinstance(detail["message"], str) and detail["message"]
    for leaked in ("NoCredentialsError", "credentials"):
        assert leaked not in err["message"]
        assert leaked not in detail["message"]


# --- GET /media/{media_id}/content ---
@dataclass(frozen=True)
class ContentCase:
    """Một ca MED-11: persona tải nội dung file đã ghi sẵn vào kho local."""

    persona: str
    alias: str
    data: bytes
    content_type: str


CONTENT_CASES = [
    pytest.param(ContentCase("demo", "gif-row", b"GIF89a" + bytes(range(64)), "image/gif"), id="a-demo-catalog-gif"),
    pytest.param(ContentCase("demo", "demo-w00-wm", _jpeg(20, 20), "image/jpeg"), id="b-demo-own-watermarked"),
    pytest.param(ContentCase("newbie", "img-dumbbell", bytes(range(100, 200)), "image/jpeg"), id="c-newbie-equipment"),
]


@pytest.mark.tc("MED-11")
@pytest.mark.parametrize("case", CONTENT_CASES)
async def test_get_media_content_local_file_returns_raw_bytes(
    media_api: MediaApi, local_storage: Path, case: ContentCase
):
    _write_object(local_storage, case.alias, case.data)
    media_id = await media_api.media_id(case.alias)

    res = await media_api.content(case.persona, media_id)

    assert res.status_code == 200, res.text
    assert res.content == case.data
    assert res.headers["content-type"].startswith(case.content_type)


@pytest.mark.tc("MED-12")
@pytest.mark.usefixtures("local_storage")
async def test_get_media_content_file_missing_in_storage_returns_404(
    media_api: MediaApi, read_object_spy: list[tuple[str, str]]
):
    gif_id = await media_api.media_id("gif-row")

    _err(await media_api.content("demo", gif_id), 404, "not_found")

    # Đã qua phân quyền nên kho được đọc đúng một lần, theo bucket/key của bản ghi DB.
    assert read_object_spy == [(DB_BUCKET, SEED_KEYS["gif-row"])]


@pytest.mark.tc("MED-12")
async def test_get_media_content_denied_media_returns_404_without_reading_storage(
    media_api: MediaApi, local_storage: Path, read_object_spy: list[tuple[str, str]]
):
    # File có thật trên kho: 404 chỉ có thể đến từ phân quyền, không phải từ việc thiếu file.
    _write_object(local_storage, "dung-w00", _jpeg(20, 20))
    _write_object(local_storage, "demo-stale", _jpeg(20, 20))

    errors = [
        _err(await media_api.content("demo", await media_api.media_id(alias)), 404, "not_found")
        for alias in ("dung-w00", "demo-stale", "missing")
    ]

    assert len({err["message"] for err in errors}) == 1
    assert read_object_spy == []


@pytest.mark.tc("MED-12")
@pytest.mark.usefixtures("local_storage")
async def test_get_media_content_storage_error_returns_503_without_leaking_error(
    media_api: MediaApi, monkeypatch: pytest.MonkeyPatch
):
    async def _broken_read(bucket: str, object_key: str) -> bytes | None:
        raise OSError("disk-hong")

    monkeypatch.setattr(storage_service, "read_object", _broken_read)
    gif_id = await media_api.media_id("gif-row")

    res = await media_api.content("demo", gif_id)

    err = _err(res, 503, "service_unavailable")
    assert len(err["details"]) == 1
    detail = err["details"][0]
    assert set(detail) == {"field", "message", "code"}
    assert (detail["field"], detail["code"]) == ("storage", "down")
    assert isinstance(detail["message"], str) and detail["message"]
    assert "disk-hong" not in res.text


# --- Đăng nhập & OpenAPI của 2 route ---
@pytest.mark.tc("MED-13")
@pytest.mark.usefixtures("local_storage")
@pytest.mark.parametrize(
    ("alias", "suffix"),
    [("gif-row", ""), ("gif-row", "/content"), ("demo-w00", "")],
    ids=["metadata-gif-row", "content-gif-row", "metadata-demo-w00"],
)
async def test_get_media_without_token_returns_401(media_api: MediaApi, alias: str, suffix: str):
    media_id = await media_api.media_id(alias)

    res = await media_api.client.get(f"{URL}/{media_id}{suffix}")

    _err(res, 401, "token_invalid")
    assert res.headers["WWW-Authenticate"] == "Bearer"


async def _revoke_newbie_roles(db: AsyncSession, redis: Redis, key: str) -> None:
    """Thu hồi mọi role của newbie trong transaction test và xoá cache quyền, để request kế tiếp đọc quyền từ DB.

    Mọi persona seed đều có quyền đọc danh mục nên phải thu hồi role. Request lỗi làm session `db` rollback về
    savepoint (`_override` trong conftest), khôi phục role đã xoá, nên phải thu hồi lại trước từng request.
    """
    await redis.delete(key)
    await db.execute(text("DELETE FROM auth.user_roles WHERE user_id = :user_id"), {"user_id": NEWBIE_ID})


@pytest.mark.tc("MED-14")
async def test_get_media_user_without_roles_returns_403_for_catalog_and_404_for_personal(
    media_api: MediaApi, local_storage: Path, newbie_perm_cache: tuple[Redis, str]
):
    redis, key = newbie_perm_cache
    # File có thật trên kho: 403 của /content chỉ có thể đến từ permission, không phải từ việc thiếu file.
    _write_object(local_storage, "gif-row", b"GIF89a" + bytes(range(16)))
    gif_id, dumbbell_id, dung_id = [await media_api.media_id(a) for a in ("gif-row", "img-dumbbell", "dung-w00")]
    headers = await media_api.auth_headers("newbie")

    for path in (f"{URL}/{gif_id}", f"{URL}/{gif_id}/content", f"{URL}/{dumbbell_id}"):
        await _revoke_newbie_roles(media_api.db, redis, key)
        _err(await media_api.client.get(path, headers=headers), 403, "permission_denied")
        # Quyền thật sự được đọc lại từ DB (không còn role) chứ không lấy từ cache cũ.
        assert json.loads(await redis.get(key)) == []
    await _revoke_newbie_roles(media_api.db, redis, key)
    # Media cá nhân của người khác rơi vào bước 4 (404 như không tồn tại), không bao giờ là 403.
    _err(await media_api.client.get(f"{URL}/{dung_id}", headers=headers), 404, "not_found")

    await _assert_cache_cleared(redis, key)


@dataclass(frozen=True)
class CachedPermissionCase:
    """Một ca MED-14 (b)/(c): cache quyền của newbie chỉ có một permission đọc danh mục."""

    permission: str
    allowed_alias: str
    denied_alias: str


CACHED_PERMISSION_CASES = [
    pytest.param(CachedPermissionCase("exercise:read", "gif-row", "img-dumbbell"), id="b-exercise-read-only"),
    pytest.param(CachedPermissionCase("equipment:read", "img-dumbbell", "gif-row"), id="c-equipment-read-only"),
]


@pytest.mark.tc("MED-14")
@pytest.mark.usefixtures("local_storage")
@pytest.mark.parametrize("case", CACHED_PERMISSION_CASES)
async def test_get_media_cached_single_permission_allows_only_matching_catalog_media(
    media_api: MediaApi, newbie_perm_cache: tuple[Redis, str], case: CachedPermissionCase
):
    redis, key = newbie_perm_cache
    await redis.set(key, json.dumps([case.permission]), ex=300)
    allowed_id = await media_api.media_id(case.allowed_alias)
    denied_id = await media_api.media_id(case.denied_alias)

    allowed_res = await media_api.get("newbie", allowed_id)
    denied_res = await media_api.get("newbie", denied_id)

    assert _ok(allowed_res)["id"] == str(allowed_id)
    _err(denied_res, 403, "permission_denied")
    await _assert_cache_cleared(redis, key)


@pytest.mark.tc("MED-15")
@pytest.mark.parametrize("path", [METADATA_PATH, CONTENT_PATH])
def test_openapi_media_route_documents_tags_errors_and_permissions(path: str):
    operation = app.openapi()["paths"][path]["get"]

    assert operation["tags"] == ["Gallery"]
    assert len(operation["summary"]) <= 80
    assert {"401", "403", "404", "422", "503"} <= set(operation["responses"])
    assert "exercise:read" in operation["description"]
    assert "equipment:read" in operation["description"]


@pytest.mark.tc("MED-15")
def test_openapi_media_metadata_route_returns_media_response_schema():
    operation = app.openapi()["paths"][METADATA_PATH]["get"]

    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("/MediaResponse")
