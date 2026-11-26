"""Truy vấn media.progress_photos + view media.v_progress_photo_cards (chức năng 4). Không commit ở đây."""

import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import StorageProvider
from app.models.media import MediaFile, ProgressPhoto

# Số đo + ngày chụp theo múi giờ user lấy từ view (doc 05 §2.2); note/created_at lấy từ bảng gốc
# vì view không có hai cột này.
_PHOTO_CARD_SQL = text(
    """
    SELECT c.photo_id AS id, c.angle, c.capture_source, c.taken_at, c.taken_date, p.note,
           c.processing_status, c.original_media_id, c.watermarked_media_id, c.thumbnail_media_id,
           c.measurement_id, c.measured_at, c.weight_kg, c.body_fat_pct, p.created_at
    FROM media.v_progress_photo_cards c
    JOIN media.progress_photos p ON p.id = c.photo_id
    WHERE c.photo_id = :photo_id AND c.user_id = :user_id
    """
)


async def get_photo_card(db: AsyncSession, user_id: uuid.UUID, photo_id: uuid.UUID) -> dict[str, Any] | None:
    """Một dòng thẻ ảnh (chưa xoá mềm) của đúng user; None nếu không có."""
    row = (await db.execute(_PHOTO_CARD_SQL, {"photo_id": photo_id, "user_id": user_id})).mappings().first()
    return dict(row) if row is not None else None


async def get_photo(db: AsyncSession, photo_id: uuid.UUID) -> ProgressPhoto | None:
    """Đọc lại ảnh từ DB, ghi đè bản trong identity map (trạng thái có thể đã đổi ngoài ORM)."""
    stmt = select(ProgressPhoto).where(ProgressPhoto.id == photo_id).execution_options(populate_existing=True)
    return await db.scalar(stmt)


async def get_media(db: AsyncSession, media_id: uuid.UUID) -> MediaFile | None:
    return await db.get(MediaFile, media_id)


async def get_media_by_key(
    db: AsyncSession, provider: StorageProvider, bucket: str, object_key: str
) -> MediaFile | None:
    """Bản ghi media đang giữ đúng (provider, bucket, object_key) — khoá uq_media_files_object."""
    stmt = select(MediaFile).where(
        MediaFile.storage_provider == provider, MediaFile.bucket == bucket, MediaFile.object_key == object_key
    )
    return await db.scalar(stmt)
