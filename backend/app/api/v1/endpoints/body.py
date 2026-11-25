"""Endpoint /body (chức năng 3): danh mục, hồ sơ thể chất, lần đo, mục tiêu."""

import uuid

from fastapi import APIRouter, Depends, Query, Response
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user, require_permission
from app.models.enums import GoalStatus
from app.schemas.base import ERROR_RESPONSES, Page
from app.schemas.body import (
    ActivityLevelResponse,
    BodyMeasurementResponse,
    BodyProfileResponse,
    BodySiteResponse,
    CreateBodyMeasurementRequest,
    CreateUserGoalRequest,
    GoalTypeResponse,
    ReplaceBodyProfileRequest,
    UpdateBodyMeasurementRequest,
    UpdateUserGoalRequest,
    UserGoalResponse,
)
from app.services import body_service

router = APIRouter(prefix="/body", tags=["Body"])

OWN = require_permission("body_metric", "manage_own")
PERM_OWN = "Quyền: `body_metric:manage_own`; chỉ thấy dữ liệu của chính mình (của người khác → 404)."


# --- Danh mục (đăng nhập) ---
@router.get(
    "/activity-levels",
    response_model=Page[ActivityLevelResponse],
    responses=ERROR_RESPONSES,
    summary="Danh sách mức độ vận động (hệ số TDEE)",
    description="Quyền: **đăng nhập**. Danh mục nhỏ, trả một trang duy nhất (`has_more=false`).",
)
async def list_activity_levels(
    _: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Page[ActivityLevelResponse]:
    return await body_service.list_activity_levels(db)


@router.get(
    "/goal-types",
    response_model=Page[GoalTypeResponse],
    responses=ERROR_RESPONSES,
    summary="Danh sách loại mục tiêu",
    description="Quyền: **đăng nhập**. Danh mục nhỏ, trả một trang duy nhất.",
)
async def list_goal_types(
    _: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Page[GoalTypeResponse]:
    return await body_service.list_goal_types(db)


@router.get(
    "/body-sites",
    response_model=Page[BodySiteResponse],
    responses=ERROR_RESPONSES,
    summary="Danh sách vị trí đo vòng",
    description="Quyền: **đăng nhập**. Danh mục nhỏ, trả một trang duy nhất.",
)
async def list_body_sites(
    _: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Page[BodySiteResponse]:
    return await body_service.list_body_sites(db)


# --- Hồ sơ thể chất ---
@router.get(
    "/profile",
    response_model=BodyProfileResponse,
    responses=ERROR_RESPONSES,
    summary="Xem hồ sơ thể chất",
    description=PERM_OWN + " Chưa có hồ sơ → các field null, `gender=unspecified`, `updated_at=null`.",
)
async def get_profile(current: CurrentUser = Depends(OWN), db: AsyncSession = Depends(get_db)) -> BodyProfileResponse:
    return await body_service.get_profile(db, current.id)


@router.put(
    "/profile",
    response_model=BodyProfileResponse,
    responses=ERROR_RESPONSES,
    summary="Tạo/thay thế hồ sơ thể chất",
    description=PERM_OWN + " PUT: gửi đủ mọi field. id danh mục không tồn tại → 422 `validation_error`.",
)
async def replace_profile(
    body: ReplaceBodyProfileRequest, current: CurrentUser = Depends(OWN), db: AsyncSession = Depends(get_db)
) -> BodyProfileResponse:
    return await body_service.replace_profile(db, current.id, body)


# --- Lần đo ---
@router.get(
    "/measurements",
    response_model=Page[BodyMeasurementResponse],
    responses=ERROR_RESPONSES,
    summary="Danh sách lần đo (mới nhất trước)",
    description=PERM_OWN + " Lọc theo `from`/`to` (ISO-8601). Mỗi lần đo kèm BMI/BMR/TDEE từ `body.v_body_metrics`.",
)
async def list_measurements(
    from_: AwareDatetime | None = Query(None, alias="from"),
    to: AwareDatetime | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> Page[BodyMeasurementResponse]:
    return await body_service.list_measurements(db, current.id, from_=from_, to=to, limit=limit, cursor=cursor)


@router.post(
    "/measurements",
    response_model=BodyMeasurementResponse,
    status_code=201,
    responses=ERROR_RESPONSES,
    summary="Cập nhật cơ thể: thêm lần đo (cân nặng, %mỡ, số đo vòng)",
    description=PERM_OWN + " Trùng `measured_at` → 409 `measurement_already_exists`. Trả kèm BMI/BMR/TDEE.",
)
async def create_measurement(
    body: CreateBodyMeasurementRequest,
    response: Response,
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> BodyMeasurementResponse:
    result = await body_service.create_measurement(db, current.id, body)
    response.headers["Location"] = f"/api/v1/body/measurements/{result.id}"
    return result


@router.get(
    "/measurements/{measurement_id}",
    response_model=BodyMeasurementResponse,
    responses=ERROR_RESPONSES,
    summary="Chi tiết một lần đo",
    description=PERM_OWN + " Không có → 404 `measurement_not_found`.",
)
async def get_measurement(
    measurement_id: uuid.UUID, current: CurrentUser = Depends(OWN), db: AsyncSession = Depends(get_db)
) -> BodyMeasurementResponse:
    return await body_service.get_measurement(db, current.id, measurement_id)


@router.patch(
    "/measurements/{measurement_id}",
    response_model=BodyMeasurementResponse,
    responses=ERROR_RESPONSES,
    summary="Sửa một phần lần đo",
    description=PERM_OWN + " Gửi `circumferences` sẽ thay thế toàn bộ số đo vòng cũ.",
)
async def update_measurement(
    measurement_id: uuid.UUID,
    body: UpdateBodyMeasurementRequest,
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> BodyMeasurementResponse:
    return await body_service.update_measurement(db, current.id, measurement_id, body)


@router.delete(
    "/measurements/{measurement_id}",
    status_code=204,
    responses=ERROR_RESPONSES,
    summary="Xoá lần đo",
    description=PERM_OWN + " Xoá luôn số đo vòng đi kèm. Trả 204 không có body.",
)
async def delete_measurement(
    measurement_id: uuid.UUID, current: CurrentUser = Depends(OWN), db: AsyncSession = Depends(get_db)
) -> Response:
    await body_service.delete_measurement(db, current.id, measurement_id)
    return Response(status_code=204)


# --- Mục tiêu ---
@router.get(
    "/goals",
    response_model=Page[UserGoalResponse],
    responses=ERROR_RESPONSES,
    summary="Danh sách mục tiêu",
    description=PERM_OWN + " Lọc `status` (active/achieved/abandoned).",
)
async def list_goals(
    status: GoalStatus | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> Page[UserGoalResponse]:
    return await body_service.list_goals(db, current.id, status=status, limit=limit, cursor=cursor)


@router.post(
    "/goals",
    response_model=UserGoalResponse,
    status_code=201,
    responses=ERROR_RESPONSES,
    summary="Tạo mục tiêu mới",
    description=PERM_OWN + " Tối đa 1 mục tiêu active → 409 `active_goal_already_exists`.",
)
async def create_goal(
    body: CreateUserGoalRequest,
    response: Response,
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> UserGoalResponse:
    result = await body_service.create_goal(db, current.id, body)
    response.headers["Location"] = f"/api/v1/body/goals/{result.id}"
    return result


@router.get(
    "/goals/{goal_id}",
    response_model=UserGoalResponse,
    responses=ERROR_RESPONSES,
    summary="Chi tiết mục tiêu",
    description=PERM_OWN + " Không có → 404 `goal_not_found`.",
)
async def get_goal(
    goal_id: uuid.UUID, current: CurrentUser = Depends(OWN), db: AsyncSession = Depends(get_db)
) -> UserGoalResponse:
    return await body_service.get_goal(db, current.id, goal_id)


@router.patch(
    "/goals/{goal_id}",
    response_model=UserGoalResponse,
    responses=ERROR_RESPONSES,
    summary="Sửa/đóng mục tiêu",
    description=PERM_OWN + " `status`: achieved | abandoned để đóng. Mục tiêu đã đóng không sửa được (422).",
)
async def update_goal(
    goal_id: uuid.UUID,
    body: UpdateUserGoalRequest,
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> UserGoalResponse:
    return await body_service.update_goal(db, current.id, goal_id, body)

