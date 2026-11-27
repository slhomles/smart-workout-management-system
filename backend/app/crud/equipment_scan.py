"""Truy vấn DB cho nhận diện thiết bị (schema `ai`). Không commit, không biết HTTP."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.equipment_scan import EquipmentScan, EquipmentScanPrediction
from app.schemas.equipment_scan import AiClassifyResult

# Top-1, ngưỡng tin cậy và thiết bị cuối cùng lấy từ view, không tự tính lại (doc 05 §2.2).
_SCAN_RESULT_SELECT = """
SELECT scan_id AS id, model_name, model_version, latency_ms, scanned_at,
       predicted_equipment_id, predicted_equipment_code, predicted_equipment_name,
       confidence, coalesce(is_confident, false) AS is_confident,
       feedback, corrected_equipment_id, resolved_equipment_id
FROM ai.v_equipment_scan_results
WHERE user_id = :user_id
"""

# Chỉ đọc danh mục để phân giải nhãn (spec §6 ý 6): thiết bị đã xoá mềm coi như không có nhãn.
_AI_LABEL_EQUIPMENT_SELECT = text("""
SELECT a.alias, eq.id
FROM catalog.equipment_aliases a
JOIN catalog.equipment eq ON eq.id = a.equipment_id AND eq.deleted_at IS NULL
WHERE a.alias_type = 'ai_label' AND a.alias = ANY(:labels)
""")

# Cùng thứ tự với top-1 của view: confidence giảm dần, hoà thì equipment_id tăng.
_SCAN_PREDICTIONS_SELECT = text("""
SELECT p.equipment_id, eq.code AS equipment_code, eq.name AS equipment_name, p.confidence
FROM ai.equipment_scan_predictions p
JOIN catalog.equipment eq ON eq.id = p.equipment_id
WHERE p.scan_id = :scan_id
ORDER BY p.confidence DESC, p.equipment_id ASC
""")


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


async def get_scan_row(db: AsyncSession, user_id: uuid.UUID, scan_id: uuid.UUID) -> Any:
    """Một dòng của view `ai.v_equipment_scan_results` (cùng cột với lịch sử quét) của user."""
    sql = _SCAN_RESULT_SELECT + " AND scan_id = :scan_id"
    return (await db.execute(text(sql), {"user_id": user_id, "scan_id": scan_id})).mappings().one()


async def list_prediction_rows(db: AsyncSession, scan_id: uuid.UUID) -> list[Any]:
    """Dự đoán đã lưu của lần quét kèm mã và tên thiết bị, sắp `confidence DESC, equipment_id ASC`."""
    return list((await db.execute(_SCAN_PREDICTIONS_SELECT, {"scan_id": scan_id})).mappings().all())


async def map_ai_labels_to_equipment(db: AsyncSession, labels: Sequence[str]) -> dict[str, int]:
    """Nhãn AI đã chuẩn hoá → id thiết bị chưa xoá mềm; nhãn không có trong danh mục thì không có mặt."""
    rows = await db.execute(_AI_LABEL_EQUIPMENT_SELECT, {"labels": list(labels)})
    return {alias: equipment_id for alias, equipment_id in rows.all()}


async def create_scan(
    db: AsyncSession,
    user_id: uuid.UUID,
    ai_result: AiClassifyResult,
    predictions: Sequence[tuple[int, float]],
) -> uuid.UUID:
    """Ghi một lần quét (không lưu ảnh) và các dự đoán `(equipment_id, confidence)`; chỉ flush, không commit."""
    scan = EquipmentScan(
        user_id=user_id,
        image_media_id=None,
        model_name=ai_result.model_name,
        model_version=ai_result.model_version,
        latency_ms=ai_result.latency_ms,
    )
    db.add(scan)
    await db.flush()
    db.add_all(
        EquipmentScanPrediction(scan_id=scan.id, equipment_id=equipment_id, confidence=confidence)
        for equipment_id, confidence in predictions
    )
    await db.flush()
    return scan.id
