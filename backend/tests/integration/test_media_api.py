"""Integration test phát media (spec be-media-delivery) trên PostgreSQL thật, rollback sau mỗi test.

Mọi test HTTP chạy với `local_storage` (file trong `tmp_path`) hoặc `s3_fake` (client S3 giả): không gọi AWS thật.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from botocore.exceptions import NoCredentialsError
from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services import storage_service

URL = "/api/v1/media"
DB_BUCKET = "smart-workout-media"
MISSING_ID = uuid.UUID("00000000-0000-4000-8000-000000000000")
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


@pytest.fixture
def media_api(client: AsyncClient, db: AsyncSession, auth_headers) -> MediaApi:
    return MediaApi(client, db, auth_headers)


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
