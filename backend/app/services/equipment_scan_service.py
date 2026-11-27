"""Nghiệp vụ /ai/equipment-scans (chức năng 7: nhận diện thiết bị phòng tập)."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import equipment_scan as crud
from app.schemas.base import Page, build_page, decode_keyset_cursor
from app.schemas.equipment_scan import EquipmentScanSummaryResponse


def _summary(row: Any) -> EquipmentScanSummaryResponse:
    return EquipmentScanSummaryResponse.model_validate(dict(row))


async def list_scans(
    db: AsyncSession, user_id: uuid.UUID, *, limit: int, cursor: str | None
) -> Page[EquipmentScanSummaryResponse]:
    """Lịch sử quét của chính user (keyset `scanned_at DESC, id DESC`); cursor hỏng → 422."""
    rows = await crud.list_scan_rows(
        db, user_id, after=decode_keyset_cursor(cursor, "scanned_at"), limit=limit + 1
    )
    return build_page(
        rows,
        limit,
        to_item=_summary,
        cursor_of=lambda r: {"scanned_at": r["scanned_at"].isoformat(), "id": str(r["id"])},
    )
