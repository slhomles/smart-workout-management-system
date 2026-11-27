"""
Nghiệp vụ Progress Gallery (chức năng 4): nhận ảnh vóc dáng, lưu Object Storage, ghi media.media_files +
media.progress_photos, đóng watermark (Ngày – Cân nặng – % Mỡ) và tạo thumbnail ngay trong request.

Gọi `storage_service.*` và `photo_watermark.*` qua thuộc tính module để test thay thế được (monkeypatch).
"""

import io
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import UploadFile
from PIL import Image, ImageOps
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import DataValidationError, ServiceUnavailableError
from app.crud import body as body_crud
from app.crud import gallery as crud
from app.models.enums import JobStatus, MediaStatus
from app.models.media import MediaFile, ProgressPhoto
from app.schemas.base import ErrorDetail, Page, build_page, decode_keyset_cursor
from app.schemas.gallery import ListProgressPhotosQuery, ProgressPhotoResponse, UploadProgressPhotoForm
from app.services import storage_service
from app.utils import photo_watermark

logger = logging.getLogger("app.gallery")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
# Dung sai lệch đồng hồ giữa điện thoại và server khi kiểm tra "chụp trong tương lai".
CLOCK_SKEW = timedelta(minutes=5)
FILENAME_MAX_LENGTH = 255
# Định dạng thật do Pillow nhận diện → (mime, đuôi file); không tin content-type của client.
ACCEPTED_FORMATS = {"JPEG": ("image/jpeg", "jpg"), "PNG": ("image/png", "png")}
GENERATED_MIME = "image/jpeg"
RETRYABLE_STATUSES = {JobStatus.QUEUED, JobStatus.FAILED}
# Thông điệp cố định: không lộ tên exception/chi tiết nội bộ (Claude_api_respone §3); chi tiết nằm ở log.
PROCESSING_ERROR_MESSAGE = "Không xử lý được ảnh"


@dataclass(frozen=True)
class _ImageInfo:
    mime_type: str
    extension: str
    width_px: int
    height_px: int


@dataclass(frozen=True)
class _RenderedImage:
    data: bytes
    width_px: int
    height_px: int


class _OriginalUnavailableError(Exception):
    """Không đọc được ảnh gốc hoặc thẻ ảnh để xử lý."""


def _invalid(field: str, message: str) -> DataValidationError:
    return DataValidationError([ErrorDetail(field=field, message=message, code="value_error")])


def _inspect_image(data: bytes) -> _ImageInfo | None:
    """Nhận diện định dạng thật + kích thước sau xoay EXIF; None nếu không phải JPEG/PNG hợp lệ."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            accepted = ACCEPTED_FORMATS.get(image.format or "")
            if accepted is None or image.width * image.height > MAX_IMAGE_PIXELS:
                return None
            ImageOps.exif_transpose(image, in_place=True)
            return _ImageInfo(accepted[0], accepted[1], image.width, image.height)
    except Exception:
        # Byte do client gửi: Pillow ném nhiều loại lỗi khác nhau (UnidentifiedImageError,
        # DecompressionBombError, SyntaxError, struct.error…) — mọi trường hợp đều là file không hợp lệ.
        logger.info("gallery: file tải lên không giải mã được", exc_info=True)
        return None


async def _read_image(upload: UploadFile) -> tuple[bytes, _ImageInfo]:
    # Đọc tối đa limit + 1 byte để biết vượt giới hạn mà không giải mã/đọc hết file lớn.
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise _invalid("file", "Ảnh vượt quá 10 MB")
    info = await run_in_threadpool(_inspect_image, data)
    if info is None:
        raise _invalid("file", "Chỉ nhận ảnh JPEG hoặc PNG hợp lệ, tối đa 40 triệu điểm ảnh")
    return data, info


async def _resolve_taken_at(db: AsyncSession, taken_at: datetime | None) -> datetime:
    now = await body_crud.db_now(db)
    if taken_at is None:
        return now
    if taken_at > now + CLOCK_SKEW:
        raise _invalid("taken_at", "Thời điểm chụp không được ở tương lai")
    return taken_at


async def _store_original(
    user_id: uuid.UUID, photo_id: uuid.UUID, data: bytes, info: _ImageInfo
) -> storage_service.StoredObject:
    key = f"users/{user_id}/progress/{photo_id}.{info.extension}"
    try:
        return await storage_service.put_object(key, data, info.mime_type)
    except Exception as exc:
        logger.exception("gallery: không lưu được ảnh gốc photo_id=%s", photo_id)
        raise ServiceUnavailableError(
            "Kho lưu trữ ảnh tạm thời không khả dụng",
            [ErrorDetail(field="storage", message="Không lưu được ảnh lên kho lưu trữ", code="down")],
        ) from exc


def _describe(media: MediaFile, stored: storage_service.StoredObject, mime_type: str, size: tuple[int, int]) -> None:
    """Ghi vào bản ghi media thông tin của file vừa lưu (thoả ck_media_files_available)."""
    media.storage_provider = stored.provider
    media.bucket = stored.bucket
    media.object_key = stored.object_key
    media.mime_type = mime_type
    media.size_bytes = stored.size_bytes
    media.checksum_sha256 = stored.checksum_sha256
    media.width_px, media.height_px = size
    media.status = MediaStatus.AVAILABLE
    media.deleted_at = None


def _render_variants(original: bytes, text: str) -> tuple[_RenderedImage, _RenderedImage]:
    """Hàm chặn (CPU): ảnh watermark rồi thumbnail tạo TỪ ảnh đã watermark (lưới ảnh in sẵn thông số)."""
    watermarked = photo_watermark.render_watermark(original, text)
    thumbnail = photo_watermark.make_thumbnail(watermarked)
    rendered = []
    for data in (watermarked, thumbnail):
        with Image.open(io.BytesIO(data)) as image:
            rendered.append(_RenderedImage(data, image.width, image.height))
    return rendered[0], rendered[1]


async def _store_generated(db: AsyncSession, object_key: str, image: _RenderedImage) -> MediaFile:
    stored = await storage_service.put_object(object_key, image.data, GENERATED_MIME)
    # Xử lý lại (ảnh queued/failed) ghi đè cùng object_key; bản ghi cũ của key đó (nếu còn) được dùng lại
    # vì uq_media_files_object không cho hai dòng cùng (provider, bucket, object_key).
    media = await crud.get_media_by_key(db, stored.provider, stored.bucket, stored.object_key)
    if media is None:
        # uploaded_by_user_id = NULL: file do hệ thống sinh, không phải user tải lên (giống seed 95).
        media = MediaFile()
        db.add(media)
    _describe(media, stored, GENERATED_MIME, (image.width_px, image.height_px))
    await db.flush()
    return media


async def _render_and_store(db: AsyncSession, photo: ProgressPhoto) -> None:
    card = await crud.get_photo_card(db, photo.user_id, photo.id)
    original = await crud.get_media(db, photo.original_media_id)
    data = await storage_service.read_object(original.bucket, original.object_key) if original else None
    if card is None or data is None:
        raise _OriginalUnavailableError("thiếu ảnh gốc hoặc thẻ ảnh")
    weight = card["weight_kg"]
    body_fat = card["body_fat_pct"]
    text = photo_watermark.watermark_text(
        card["taken_date"], float(weight) if weight is not None else None,
        float(body_fat) if body_fat is not None else None,
    )
    watermarked, thumbnail = await run_in_threadpool(_render_variants, data, text)
    prefix = f"users/{photo.user_id}/progress/{photo.id}"
    watermarked_media = await _store_generated(db, f"{prefix}.wm.jpg", watermarked)
    thumbnail_media = await _store_generated(db, f"{prefix}.thumb.jpg", thumbnail)
    photo.watermarked_media_id = watermarked_media.id
    photo.thumbnail_media_id = thumbnail_media.id
    photo.processing_status = JobStatus.COMPLETED
    photo.processing_error = None
    photo.updated_at = func.now()
    await db.flush()


async def _process(db: AsyncSession, photo: ProgressPhoto) -> None:
    """Đóng watermark + thumbnail; lỗi bất kỳ → `failed`, KHÔNG ném ra ngoài. Không commit."""
    if photo.processing_status not in RETRYABLE_STATUSES:
        return
    photo_id = photo.id
    try:
        # Savepoint: lỗi giữa chừng chỉ huỷ phần ghi của bước xử lý, session vẫn dùng tiếp được.
        async with db.begin_nested():
            await _render_and_store(db, photo)
    except Exception:
        logger.exception("gallery: xử lý ảnh thất bại photo_id=%s", photo_id)
        photo.watermarked_media_id = None
        photo.thumbnail_media_id = None
        photo.processing_status = JobStatus.FAILED
        photo.processing_error = PROCESSING_ERROR_MESSAGE
        photo.updated_at = func.now()
        await db.flush()


async def process_photo(db: AsyncSession, photo_id: uuid.UUID) -> None:
    """Đóng watermark + thumbnail cho ảnh `queued`/`failed` rồi commit; ảnh trạng thái khác giữ nguyên.

    Không ném lỗi xử lý ảnh: thất bại được ghi thành `processing_status='failed'` (worker gọi lại được).
    """
    photo = await crud.get_photo(db, photo_id)
    if photo is None:
        logger.warning("gallery: không có ảnh để xử lý photo_id=%s", photo_id)
        return
    await _process(db, photo)
    await db.commit()


async def upload_photo(
    db: AsyncSession, user_id: uuid.UUID, upload: UploadFile, form: UploadProgressPhotoForm
) -> ProgressPhotoResponse:
    """Kiểm tra file + form, lưu ảnh gốc, ghi 2 bảng, xử lý ảnh và commit một lần."""
    data, info = await _read_image(upload)
    taken_at = await _resolve_taken_at(db, form.taken_at)
    photo_id = uuid.uuid4()
    stored = await _store_original(user_id, photo_id, data, info)
    original = MediaFile(uploaded_by_user_id=user_id, original_filename=(upload.filename or "")[:FILENAME_MAX_LENGTH] or None)
    _describe(original, stored, info.mime_type, (info.width_px, info.height_px))
    db.add(original)
    await db.flush()
    photo = ProgressPhoto(
        id=photo_id, user_id=user_id, original_media_id=original.id, angle=form.angle,
        capture_source=form.capture_source, taken_at=taken_at, processing_status=JobStatus.QUEUED, note=form.note,
    )
    db.add(photo)
    await db.flush()
    await _process(db, photo)
    await db.commit()
    card = await crud.get_photo_card(db, user_id, photo_id)
    return ProgressPhotoResponse.model_validate(card)


async def list_photos(
    db: AsyncSession, user_id: uuid.UUID, query: ListProgressPhotosQuery
) -> Page[ProgressPhotoResponse]:
    """Lưới ảnh chưa xoá mềm của user, mới chụp trước (keyset `taken_at DESC, id DESC`)."""
    # Lấy thêm 1 dòng để biết còn trang sau mà không COUNT(*) (Claude_api_respone §5).
    window = crud.KeysetWindow(after=decode_keyset_cursor(query.cursor, "taken_at"), limit=query.limit + 1)
    rows = await crud.list_photo_cards(db, user_id, query.angle, window)
    return build_page(
        rows,
        query.limit,
        to_item=ProgressPhotoResponse.model_validate,
        cursor_of=lambda r: {"taken_at": r["taken_at"].isoformat(), "id": str(r["id"])},
    )
