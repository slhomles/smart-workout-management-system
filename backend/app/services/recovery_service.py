"""Nghiệp vụ /recovery (chức năng 2): Heatmap phục hồi và lịch sử dự đoán phục hồi.

Giá trị phục hồi (%, giờ còn lại, trạng thái) lấy nguyên từ view, không tính lại (doc 05 §2.2).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DataValidationError
from app.crud import recovery as crud
from app.schemas.base import ErrorDetail, Page, build_page, decode_cursor
from app.schemas.recovery import (
    MuscleRecoveryListQuery,
    MuscleRecoveryStatusResponse,
    RecoveryPredictionListQuery,
    RecoveryPredictionResponse,
)

_INVALID_CURSOR = ErrorDetail(field="cursor", message="Cursor không hợp lệ", code="invalid_cursor")
# Khoảng giá trị của catalog.muscle_groups.id (smallint); ngoài khoảng này cursor chắc chắn bị sửa tay.
_MUSCLE_GROUP_ID_MAX = 32767


def _muscle_group_id_of(values: dict[str, Any]) -> int:
    """`muscle_group_id` của cursor phải là int thật (bool cũng là int trong Python nên loại riêng)."""
    value = values["muscle_group_id"]
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= _MUSCLE_GROUP_ID_MAX:
        raise ValueError("muscle_group_id")
    return value


def _decode_muscle_cursor(cursor: str | None) -> int | None:
    """Cursor dạng {"muscle_group_id": n} cho sắp xếp `muscle_group_id ASC`."""
    if cursor is None:
        return None
    try:
        return _muscle_group_id_of(decode_cursor(cursor))
    except (KeyError, ValueError):
        raise DataValidationError([_INVALID_CURSOR]) from None


def _decode_prediction_cursor(cursor: str | None) -> crud.PredictionPosition | None:
    """Cursor dạng {"trained_at": ISO có múi giờ, "session_id": uuid, "muscle_group_id": n}."""
    if cursor is None:
        return None
    values = decode_cursor(cursor)
    try:
        trained_at = datetime.fromisoformat(values["trained_at"])
        session_id = uuid.UUID(values["session_id"])
        muscle_group_id = _muscle_group_id_of(values)
    except (KeyError, ValueError, TypeError, AttributeError):
        raise DataValidationError([_INVALID_CURSOR]) from None
    # So với cột timestamptz, mốc không có múi giờ sẽ bị hiểu theo giờ máy chủ: coi là cursor hỏng.
    if trained_at.tzinfo is None:
        raise DataValidationError([_INVALID_CURSOR])
    return trained_at, session_id, muscle_group_id


async def list_muscle_recovery(
    db: AsyncSession, user_id: uuid.UUID, query: MuscleRecoveryListQuery
) -> Page[MuscleRecoveryStatusResponse]:
    """Trang Heatmap của chính user: mọi nhóm cơ có `heatmap_region_key`, lọc `recovery_status`."""
    rows = await crud.list_muscle_recovery(db, user_id, query, _decode_muscle_cursor(query.cursor))
    return build_page(
        rows,
        query.limit,
        to_item=lambda row: MuscleRecoveryStatusResponse.model_validate(dict(row)),
        cursor_of=lambda row: {"muscle_group_id": row["muscle_group_id"]},
    )


async def list_predictions(
    db: AsyncSession, user_id: uuid.UUID, query: RecoveryPredictionListQuery
) -> Page[RecoveryPredictionResponse]:
    """Lịch sử dự đoán của chính user (bản mới nhất mỗi buổi × nhóm cơ), buổi tập gần nhất trước."""
    rows = await crud.list_prediction_history(db, user_id, query, _decode_prediction_cursor(query.cursor))
    return build_page(
        rows,
        query.limit,
        to_item=lambda row: RecoveryPredictionResponse.model_validate(dict(row)),
        cursor_of=lambda row: {
            "trained_at": row["trained_at"].isoformat(),
            "session_id": str(row["session_id"]),
            "muscle_group_id": row["muscle_group_id"],
        },
    )
