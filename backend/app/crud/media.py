"""Truy vấn phát media: media.media_files, media.progress_photos và tham chiếu danh mục (chỉ đọc).

Module chỉ đọc DB, không ghi, không commit. Tham chiếu danh mục đọc chéo bằng `text()` vì `catalog_service`
không có hàm cho nhu cầu này (spec be-media-delivery §6 ý 9, tiền lệ `crud/video_job.py`); không import
crud/model của Catalog.
"""

import uuid

from sqlalchemy import exists, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MediaStatus
from app.models.media import MediaFile, ProgressPhoto

EXERCISE_REFERENCE = "exercise"
EQUIPMENT_REFERENCE = "equipment"

# Chỉ tính tham chiếu từ nội dung danh mục còn hiển thị cho user: bài tập đã xuất bản chưa xoá, thiết bị chưa xoá.
_CATALOG_REFERENCES_SQL = text(
    """
    SELECT 'exercise' AS kind
    WHERE EXISTS (
        SELECT 1
        FROM catalog.exercise_media em
        JOIN catalog.exercises e ON e.id = em.exercise_id
        WHERE em.media_id = :media_id AND e.status = 'published' AND e.deleted_at IS NULL
    )
    UNION ALL
    SELECT 'equipment' AS kind
    WHERE EXISTS (
        SELECT 1
        FROM catalog.equipment eq
        WHERE eq.image_media_id = :media_id AND eq.deleted_at IS NULL
    )
    """
)


async def get_available_media(db: AsyncSession, media_id: uuid.UUID) -> MediaFile | None:
    """Media chưa xoá mềm và đang `available`; None nếu không có."""
    stmt = select(MediaFile).where(
        MediaFile.id == media_id,
        MediaFile.deleted_at.is_(None),
        MediaFile.status == MediaStatus.AVAILABLE,
    )
    return await db.scalar(stmt)


async def is_progress_photo_media_of_user(db: AsyncSession, media_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Media là ảnh gốc, ảnh watermark hoặc thumbnail của một ảnh tiến độ thuộc user.

    Không lọc `deleted_at` của ảnh tiến độ: xoá mềm ảnh không đổi chủ sở hữu file (spec §6 ý 3).
    """
    stmt = select(
        exists().where(
            ProgressPhoto.user_id == user_id,
            or_(
                ProgressPhoto.original_media_id == media_id,
                ProgressPhoto.watermarked_media_id == media_id,
                ProgressPhoto.thumbnail_media_id == media_id,
            ),
        )
    )
    return bool(await db.scalar(stmt))


async def get_catalog_reference_kinds(db: AsyncSession, media_id: uuid.UUID) -> set[str]:
    """Các loại nội dung danh mục còn hiển thị đang dùng media: tập con của {"exercise", "equipment"}."""
    rows = await db.execute(_CATALOG_REFERENCES_SQL, {"media_id": media_id})
    return set(rows.scalars())
