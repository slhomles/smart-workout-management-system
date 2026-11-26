"""Endpoint /reports (chức năng 3, bước 5): xuất thẻ báo cáo tuần/tháng."""

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.models.enums import ReportType
from app.schemas.base import ERROR_RESPONSES, Page
from app.schemas.report import CreateReportExportRequest, ReportExportResponse
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["Reports"])

OWN = require_permission("report", "export_own")
PERM = "Quyền: `report:export_own`; chỉ thấy báo cáo của chính mình."


@router.post(
    "",
    response_model=ReportExportResponse,
    status_code=201,
    responses=ERROR_RESPONSES,
    summary="Xuất báo cáo tuần/tháng thành ảnh PNG",
    description=(
        PERM + " Tổng hợp số liệu kỳ, vẽ thẻ 1080×1920 và lưu Object Storage. `period_start` phải là thứ Hai "
        "(tuần) hoặc ngày 1 (tháng), không ở tương lai → 422. Đã xuất kỳ này → 409 `report_already_exists`."
    ),
)
async def create_report(
    body: CreateReportExportRequest,
    response: Response,
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> ReportExportResponse:
    result = await report_service.create_report(db, current.id, body)
    response.headers["Location"] = f"/api/v1/reports/{result.id}"
    return result


@router.get(
    "",
    response_model=Page[ReportExportResponse],
    responses=ERROR_RESPONSES,
    summary="Danh sách báo cáo đã xuất",
    description=PERM + " Lọc `report_type`. Mới nhất trước.",
)
async def list_reports(
    report_type: ReportType | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> Page[ReportExportResponse]:
    return await report_service.list_reports(db, current.id, report_type=report_type, limit=limit, cursor=cursor)


@router.get(
    "/{report_id}",
    response_model=ReportExportResponse,
    responses=ERROR_RESPONSES,
    summary="Chi tiết báo cáo",
    description=PERM + " Không có → 404 `report_not_found`.",
)
async def get_report(
    report_id: uuid.UUID, current: CurrentUser = Depends(OWN), db: AsyncSession = Depends(get_db)
) -> ReportExportResponse:
    return await report_service.get_report(db, current.id, report_id)


@router.get(
    "/{report_id}/image",
    response_class=Response,
    responses={**ERROR_RESPONSES, 200: {"content": {"image/png": {}}, "description": "Ảnh PNG của thẻ báo cáo"}},
    summary="Tải ảnh thẻ báo cáo",
    description=PERM + " Trả file ảnh (không bọc JSON). File không còn trên kho lưu trữ → 404 `report_not_found`.",
)
async def get_report_image(
    report_id: uuid.UUID, current: CurrentUser = Depends(OWN), db: AsyncSession = Depends(get_db)
) -> Response:
    data, mime = await report_service.get_report_image(db, current.id, report_id)
    return Response(content=data, media_type=mime)
