"""Truy vấn media.progress_photos, media.photo_comparisons + view media.v_progress_photo_cards (chức năng 4).

Không commit ở đây.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PhotoAngle, StorageProvider
from app.models.media import MediaFile, PhotoComparison, ProgressPhoto

# Số đo + ngày chụp theo múi giờ user lấy từ view (doc 05 §2.2); note/created_at lấy từ bảng gốc
# vì view không có hai cột này. View đã loại ảnh xoá mềm.
_PHOTO_CARD_SELECT = """
    SELECT c.photo_id AS id, c.angle, c.capture_source, c.taken_at, c.taken_date, p.note,
           c.processing_status, c.original_media_id, c.watermarked_media_id, c.thumbnail_media_id,
           c.measurement_id, c.measured_at, c.weight_kg, c.body_fat_pct, p.created_at
    FROM media.v_progress_photo_cards c
    JOIN media.progress_photos p ON p.id = c.photo_id
"""
_PHOTO_CARD_SQL = text(_PHOTO_CARD_SELECT + " WHERE c.photo_id = :photo_id AND c.user_id = :user_id")
_PHOTO_CARDS_SQL = text(_PHOTO_CARD_SELECT + " WHERE c.photo_id = ANY(:photo_ids) AND c.user_id = :user_id")
# Điều kiện tuỳ chọn là đoạn SQL cố định; giá trị luôn đi qua bind param.
_ANGLE_FILTER = "c.angle = CAST(:angle AS media.photo_angle)"
_KEYSET_FILTER = "(c.taken_at, c.photo_id) < (:after_ts, :after_id)"


async def get_photo_card(db: AsyncSession, user_id: uuid.UUID, photo_id: uuid.UUID) -> dict[str, Any] | None:
    """Một dòng thẻ ảnh (chưa xoá mềm) của đúng user; None nếu không có."""
    row = (await db.execute(_PHOTO_CARD_SQL, {"photo_id": photo_id, "user_id": user_id})).mappings().first()
    return dict(row) if row is not None else None


@dataclass(frozen=True)
class KeysetWindow:
    """Một lát keyset: các dòng đứng sau `after` = (khoá sắp xếp, id) (None = từ đầu), tối đa `limit` dòng.

    Khoá sắp xếp là `taken_at` với ảnh, `created_at` với cặp so sánh; luôn theo thứ tự (khoá DESC, id DESC).
    """

    after: tuple[datetime, uuid.UUID] | None
    limit: int


async def list_photo_cards(
    db: AsyncSession, user_id: uuid.UUID, angle: PhotoAngle | None, window: KeysetWindow
) -> list[dict[str, Any]]:
    """Thẻ ảnh của user theo (taken_at DESC, id DESC), lọc `angle` nếu có."""
    conditions = ["c.user_id = :user_id"]
    params: dict[str, Any] = {"user_id": user_id, "limit": window.limit}
    if angle is not None:
        conditions.append(_ANGLE_FILTER)
        params["angle"] = angle.value
    if window.after is not None:
        conditions.append(_KEYSET_FILTER)
        params.update(after_ts=window.after[0], after_id=window.after[1])
    where = " AND ".join(conditions)
    stmt = text(f"{_PHOTO_CARD_SELECT} WHERE {where} ORDER BY c.taken_at DESC, c.photo_id DESC LIMIT :limit")
    return [dict(row) for row in (await db.execute(stmt, params)).mappings().all()]


async def get_photo_cards(
    db: AsyncSession, user_id: uuid.UUID, photo_ids: list[uuid.UUID]
) -> list[dict[str, Any]]:
    """Thẻ ảnh (chưa xoá mềm) của đúng user cho nhiều id một lần; id không khớp bị bỏ qua."""
    params = {"photo_ids": photo_ids, "user_id": user_id}
    return [dict(row) for row in (await db.execute(_PHOTO_CARDS_SQL, params)).mappings().all()]


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


# Chủ sở hữu cặp suy ra từ ảnh (bảng không có user_id); JOIN view nên cặp có ảnh đã xoá mềm bị ẩn.
_COMPARISON_SELECT = """
    SELECT pc.id, pc.title, pc.created_at, pc.before_photo_id, pc.after_photo_id
    FROM media.photo_comparisons pc
    JOIN media.v_progress_photo_cards b ON b.photo_id = pc.before_photo_id AND b.user_id = :user_id
    JOIN media.v_progress_photo_cards a ON a.photo_id = pc.after_photo_id AND a.user_id = :user_id
"""
_COMPARISON_KEYSET_FILTER = " WHERE (pc.created_at, pc.id) < (:after_ts, :after_id)"
_COMPARISON_ORDER = " ORDER BY pc.created_at DESC, pc.id DESC LIMIT :limit"


async def comparison_exists(db: AsyncSession, before_photo_id: uuid.UUID, after_photo_id: uuid.UUID) -> bool:
    """Đã có cặp (before, after) này chưa — khoá uq_photo_comparisons_pair."""
    stmt = select(PhotoComparison.id).where(
        PhotoComparison.before_photo_id == before_photo_id, PhotoComparison.after_photo_id == after_photo_id
    )
    return await db.scalar(stmt) is not None


async def add_comparison(
    db: AsyncSession, before_photo_id: uuid.UUID, after_photo_id: uuid.UUID, title: str | None
) -> PhotoComparison:
    """Thêm một cặp so sánh, flush và nạp lại cột do DB sinh (id, created_at)."""
    comparison = PhotoComparison(before_photo_id=before_photo_id, after_photo_id=after_photo_id, title=title)
    db.add(comparison)
    await db.flush()
    await db.refresh(comparison)
    return comparison


async def list_comparisons(db: AsyncSession, user_id: uuid.UUID, window: KeysetWindow) -> list[dict[str, Any]]:
    """Cặp so sánh mà cả hai ảnh thuộc user và chưa xoá mềm, theo (created_at DESC, id DESC)."""
    params: dict[str, Any] = {"user_id": user_id, "limit": window.limit}
    keyset = ""
    if window.after is not None:
        keyset = _COMPARISON_KEYSET_FILTER
        params.update(after_ts=window.after[0], after_id=window.after[1])
    stmt = text(_COMPARISON_SELECT + keyset + _COMPARISON_ORDER)
    return [dict(row) for row in (await db.execute(stmt, params)).mappings().all()]
