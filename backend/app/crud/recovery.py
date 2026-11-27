"""Truy vấn phục hồi cơ: view training.v_muscle_recovery_status và bảng training.recovery_predictions.

Đọc bằng `text()`: view tính sẵn % hồi phục và trạng thái (doc 05 §2.2: không tự tính lại), còn
catalog.muscle_groups là bảng danh mục chỉ đọc của module khác. Không commit (chỉ đọc).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.recovery import MuscleRecoveryListQuery, RecoveryPredictionListQuery

# Vị trí sau phần tử cuối của trang trước, theo thứ tự `trained_at DESC, session_id DESC, muscle_group_id ASC`.
PredictionPosition = tuple[datetime, uuid.UUID, int]

_MUSCLE_RECOVERY_SELECT = """
SELECT muscle_group_id, muscle_code, muscle_name, heatmap_region_key, recovery_status, recovery_pct,
       remaining_hours, fatigue_score, last_trained_at, recovered_at, last_session_id, model_version
FROM training.v_muscle_recovery_status
WHERE user_id = :user_id
"""

# Mỗi (buổi, nhóm cơ) chỉ giữ bản chạy dự đoán gần nhất; model_version phá hoà để kết quả ổn định.
_LATEST_PREDICTIONS_CTE = """
WITH latest AS (
    SELECT DISTINCT ON (rp.session_id, rp.muscle_group_id)
        rp.session_id, s.name AS session_name, coalesce(s.ended_at, s.started_at) AS trained_at,
        rp.muscle_group_id, mg.code AS muscle_code, mg.name AS muscle_name,
        rp.model_version, rp.fatigue_score, rp.recovered_at, rp.predicted_at
    FROM training.recovery_predictions rp
    JOIN training.workout_sessions s
      ON s.id = rp.session_id AND s.user_id = :user_id AND s.deleted_at IS NULL
    JOIN catalog.muscle_groups mg ON mg.id = rp.muscle_group_id
    WHERE {muscle_filter}
    ORDER BY rp.session_id, rp.muscle_group_id, rp.predicted_at DESC, rp.model_version DESC
)
SELECT * FROM latest
"""

# Keyset cho thứ tự hỗn hợp DESC/DESC/ASC: không gộp được thành một phép so sánh tuple.
_PREDICTION_AFTER = """
WHERE trained_at < :c_at
   OR (trained_at = :c_at AND session_id < :c_session)
   OR (trained_at = :c_at AND session_id = :c_session AND muscle_group_id > :c_muscle)
"""


async def list_muscle_recovery(
    db: AsyncSession,
    user_id: uuid.UUID,
    query: MuscleRecoveryListQuery,
    after_muscle_group_id: int | None,
) -> list[Any]:
    """Một trang Heatmap của user, sắp `muscle_group_id ASC`.

    Lấy `limit + 1` dòng để tầng service biết còn trang sau mà không cần COUNT(*).
    """
    sql = _MUSCLE_RECOVERY_SELECT
    params: dict[str, Any] = {"user_id": user_id, "limit": query.limit + 1}
    if query.recovery_status is not None:
        sql += " AND recovery_status = :recovery_status"
        params["recovery_status"] = query.recovery_status
    if after_muscle_group_id is not None:
        sql += " AND muscle_group_id > :after"
        params["after"] = after_muscle_group_id
    sql += " ORDER BY muscle_group_id LIMIT :limit"
    return list((await db.execute(text(sql), params)).mappings().all())


async def list_prediction_history(
    db: AsyncSession,
    user_id: uuid.UUID,
    query: RecoveryPredictionListQuery,
    after: PredictionPosition | None,
) -> list[Any]:
    """Một trang lịch sử dự đoán của user (buổi chưa xoá), mới nhất trước; lấy `limit + 1` dòng."""
    params: dict[str, Any] = {"user_id": user_id, "limit": query.limit + 1}
    muscle_filter = "TRUE"
    if query.muscle_group_id is not None:
        muscle_filter = "rp.muscle_group_id = :muscle_group_id"
        params["muscle_group_id"] = query.muscle_group_id
    sql = _LATEST_PREDICTIONS_CTE.format(muscle_filter=muscle_filter)
    if after is not None:
        sql += _PREDICTION_AFTER
        params["c_at"], params["c_session"], params["c_muscle"] = after
    sql += " ORDER BY trained_at DESC, session_id DESC, muscle_group_id ASC LIMIT :limit"
    return list((await db.execute(text(sql), params)).mappings().all())
