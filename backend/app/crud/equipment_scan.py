"""Truy vấn DB cho nhận diện thiết bị (schema `ai`). Không commit, không biết HTTP."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Top-1, ngưỡng tin cậy và thiết bị cuối cùng lấy từ view, không tự tính lại (doc 05 §2.2).
_SCAN_RESULT_SELECT = """
SELECT scan_id AS id, model_name, model_version, latency_ms, scanned_at,
       predicted_equipment_id, predicted_equipment_code, predicted_equipment_name,
       confidence, coalesce(is_confident, false) AS is_confident,
       feedback, corrected_equipment_id, resolved_equipment_id
FROM ai.v_equipment_scan_results
WHERE user_id = :user_id
"""


async def list_scan_rows(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[Any]:
    """Lịch sử quét của user, sắp `scanned_at DESC, id DESC`, bắt đầu sau vị trí keyset `after`."""
    sql = _SCAN_RESULT_SELECT
    params: dict[str, Any] = {"user_id": user_id, "limit": limit}
    if after is not None:
        sql += " AND (scanned_at, scan_id) < (:after_at, :after_id)"
        params["after_at"], params["after_id"] = after
    sql += " ORDER BY scanned_at DESC, scan_id DESC LIMIT :limit"
    return list((await db.execute(text(sql), params)).mappings().all())
