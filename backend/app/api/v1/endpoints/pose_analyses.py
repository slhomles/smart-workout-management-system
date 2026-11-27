"""Endpoint /ai/pose-analyses (chức năng 5): lưu và tra cứu kết quả phân tích tư thế của chính user."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.schemas.base import ERROR_RESPONSES, Page
from app.schemas.pose_analysis import CreatePoseAnalysisRequest, PoseAnalysisFilter, PoseAnalysisResponse
from app.services import pose_analysis_service

router = APIRouter(prefix="/ai/pose-analyses", tags=["AI"])

USE_AI = require_permission("ai", "use")
PERM = "Quyền: `ai:use`; chỉ trên hiệp tập của chính mình (của người khác → 404)."


@router.post(
    "",
    response_model=PoseAnalysisResponse,
    status_code=201,
    responses=ERROR_RESPONSES,
    summary="Lưu kết quả phân tích tư thế realtime của một hiệp",
    description=(
        PERM
        + " Ghi `ai.pose_analyses` (`mode = realtime_edge`) và 0..500 lỗi tư thế trong một transaction."
        " Lỗi: 404 `exercise_set_not_found` (hiệp không có, của user khác hoặc buổi đã xoá);"
        " 422 `validation_error` (sai dữ liệu, `analyzed_at` muộn hơn giờ server quá 5 phút,"
        " bài không hỗ trợ AI, mã lỗi không thuộc bài của hiệp); 401 `token_invalid`; 403 `permission_denied`."
    ),
)
async def create_pose_analysis(
    body: CreatePoseAnalysisRequest,
    response: Response,
    current: CurrentUser = Depends(USE_AI),
    db: AsyncSession = Depends(get_db),
) -> PoseAnalysisResponse:
    result = await pose_analysis_service.create_analysis(db, current.id, body)
    response.headers["Location"] = f"/api/v1/ai/pose-analyses/{result.id}"
    return result


@router.get(
    "",
    response_model=Page[PoseAnalysisResponse],
    status_code=200,
    responses=ERROR_RESPONSES,
    summary="Danh sách phân tích tư thế của tôi (mới nhất trước)",
    description=(
        "Quyền: `ai:use`; chỉ trả phân tích trên hiệp tập của chính mình (admin cũng vậy)."
        " Gồm cả `realtime_edge` và `video_server`, mỗi phần tử kèm danh sách lỗi; ẩn buổi tập đã xoá."
        " Sắp `created_at` giảm dần. Lọc `set_id`, `exercise_id`, `mode`; phân trang `limit` (1–100,"
        " mặc định 20) + `cursor`. Không có kết quả → 200 `data: []`."
        " Lỗi: 422 `validation_error` (tham số sai kiểu/ngoài khoảng, cursor hỏng);"
        " 401 `token_invalid`; 403 `permission_denied`."
    ),
)
async def list_pose_analyses(
    filters: Annotated[PoseAnalysisFilter, Query()],
    current: CurrentUser = Depends(USE_AI),
    db: AsyncSession = Depends(get_db),
) -> Page[PoseAnalysisResponse]:
    return await pose_analysis_service.list_analyses(db, current.id, filters)
