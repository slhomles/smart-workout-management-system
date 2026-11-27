"""Endpoint /ai/equipment-scans (chức năng 7): nhận diện thiết bị phòng tập."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.schemas.base import ERROR_RESPONSES, Page
from app.schemas.equipment_scan import EquipmentScanSummaryResponse
from app.services import equipment_scan_service

router = APIRouter(prefix="/ai/equipment-scans", tags=["AI"])

AI_USE = require_permission("ai", "use")


@router.get(
    "",
    response_model=Page[EquipmentScanSummaryResponse],
    status_code=200,
    responses=ERROR_RESPONSES,
    summary="Lịch sử quét thiết bị của tôi (mới nhất trước)",
    description=(
        "Quyền: `ai:use`. Trả các lần quét của **chính user đang đăng nhập** (admin cũng chỉ thấy của mình), "
        "sắp `scanned_at` giảm dần rồi `id` giảm dần, phân trang cursor (`limit` 1–100, mặc định 20). "
        "Mỗi phần tử kèm thiết bị top-1, `confidence`, `is_confident` (≥ 0.60) và `resolved_equipment_id`. "
        "Lỗi: 422 `validation_error` (`limit`/`cursor` sai), 401 `token_invalid`, 403 `permission_denied`."
    ),
)
async def list_equipment_scans(
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    current: CurrentUser = Depends(AI_USE),
    db: AsyncSession = Depends(get_db),
) -> Page[EquipmentScanSummaryResponse]:
    return await equipment_scan_service.list_scans(db, current.id, limit=limit, cursor=cursor)
