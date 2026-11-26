"""Endpoint /dashboard (chức năng 3): tổng quan trong ngày, xu hướng cân nặng."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.schemas.base import ERROR_RESPONSES
from app.schemas.dashboard import DashboardResponse, TrendRange, WeightTrendResponse
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Body"])

OWN = require_permission("body_metric", "manage_own")


@router.get(
    "",
    response_model=DashboardResponse,
    responses=ERROR_RESPONSES,
    summary="Tổng quan Dashboard trong ngày",
    description=(
        "Quyền: `body_metric:manage_own`. Chỉ số cơ thể mới nhất (BMI/BMR/TDEE), mục tiêu đang theo, "
        "calo tiêu hao & volume hôm nay, tiến độ lịch tập tuần này, cờ chững cân. Ngày tính theo múi giờ user. "
        "Không có calo nạp vào (Food Control ngoài phạm vi)."
    ),
)
async def get_dashboard(current: CurrentUser = Depends(OWN), db: AsyncSession = Depends(get_db)) -> DashboardResponse:
    return await dashboard_service.get_dashboard(db, current.id)


@router.get(
    "/weight-trend",
    response_model=WeightTrendResponse,
    responses=ERROR_RESPONSES,
    summary="Xu hướng cân nặng theo tuần (Tháng / 3 Tháng)",
    description=(
        "Quyền: `body_metric:manage_own`. `range`: week | month (5 tuần) | 3months (13 tuần). "
        "Mỗi điểm là một tuần: cân nặng TB, chênh lệch, `is_plateau`, số buổi và calo tiêu hao."
    ),
)
async def get_weight_trend(
    range_: TrendRange = Query("month", alias="range"),
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> WeightTrendResponse:
    return await dashboard_service.get_weight_trend(db, current.id, range_)
