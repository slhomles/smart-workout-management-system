"""Endpoint chức năng 2 (Workout Routine): giáo án, lịch tập, trạng thái phục hồi nhóm cơ.

Một `router` gộp 3 router con theo tiền tố của doc 05 §6.3: `/workout-plans`,
`/scheduled-workouts`, `/recovery`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.schemas.base import ERROR_RESPONSES, Page
from app.schemas.workout_routine import WorkoutPlanListQuery, WorkoutPlanResponse
from app.services import workout_plan_service

OWN = require_permission("workout", "manage_own")
PERM = "Quyền: `workout:manage_own`; chỉ thấy và thao tác trên dữ liệu của chính mình."

plans_router = APIRouter(prefix="/workout-plans", tags=["Workouts"])
schedules_router = APIRouter(prefix="/scheduled-workouts", tags=["Workouts"])
recovery_router = APIRouter(prefix="/recovery", tags=["Workouts"])


# --- Giáo án ---
@plans_router.get(
    "",
    response_model=Page[WorkoutPlanResponse],
    status_code=200,
    responses=ERROR_RESPONSES,
    summary="Danh sách giáo án của tôi (kèm buổi và bài)",
    description=PERM
    + " Chỉ gồm giáo án của chính user: không gồm giáo án mẫu và giáo án đã xoá mềm."
    " Mỗi giáo án kèm đầy đủ buổi (theo `day_no`) và bài (theo `order_no`)."
    " Sắp `created_at` giảm dần; lọc `status`; phân trang cursor (`limit` 1–100, mặc định 20).",
)
async def list_workout_plans(
    query: Annotated[WorkoutPlanListQuery, Query()],
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> Page[WorkoutPlanResponse]:
    """Liệt kê giáo án của user đang đăng nhập."""
    return await workout_plan_service.list_plans(db, current.id, query)


# Gộp sau khi khai báo route: include_router sao chép các route đang có tại thời điểm gọi.
router = APIRouter()
router.include_router(plans_router)
router.include_router(schedules_router)
router.include_router(recovery_router)
