"""Endpoint /ai/video-jobs (chức năng 6, luồng video 1B): gửi video của một hiệp để AI đếm rep, đo tempo."""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.models.enums import JobStatus
from app.schemas.base import ERROR_RESPONSES, Page
from app.schemas.video_job import BIGINT_MAX, CreateVideoJobRequest, VideoJobListQuery, VideoJobResponse
from app.services import video_job_service

router = APIRouter(prefix="/ai/video-jobs", tags=["AI"])

AI_USE = require_permission("ai", "use")
PERM = "Quyền: `ai:use`; chỉ thao tác trên hiệp tập và video của chính mình."


@router.post(
    "",
    response_model=VideoJobResponse,
    status_code=202,
    responses=ERROR_RESPONSES,
    summary="Gửi video của một hiệp để AI đếm rep và đo tempo",
    description=(
        PERM + " Tạo job `queued` xử lý bất đồng bộ, trả 202 + `Location`. Hiệp không có/của người khác/"
        "buổi đã xoá → 404 `exercise_set_not_found`. Bài chưa hỗ trợ AI hoặc video không hợp lệ "
        "(không có, không phải video, chưa sẵn sàng, đã xoá, của người khác) → 422 `validation_error`. "
        "Thiếu/sai token → 401 `token_invalid`; thiếu quyền → 403 `permission_denied`."
    ),
)
async def create_job(
    body: CreateVideoJobRequest,
    response: Response,
    current: CurrentUser = Depends(AI_USE),
    db: AsyncSession = Depends(get_db),
) -> VideoJobResponse:
    """Tạo job phân tích video cho một hiệp của user đang đăng nhập."""
    result = await video_job_service.create_job(db, current.id, body)
    response.headers["Location"] = f"/api/v1/ai/video-jobs/{result.id}"
    return result


@router.get(
    "",
    response_model=Page[VideoJobResponse],
    status_code=200,
    responses=ERROR_RESPONSES,
    summary="Danh sách job phân tích video của tôi (mới nhất trước)",
    description=(
        PERM + " Sắp `created_at` giảm dần. Lọc `status` (queued|processing|completed|failed|cancelled), "
        "`set_id`; phân trang cursor `limit` (1..100, mặc định 20) + `cursor`. Hiệp của người khác/"
        "buổi đã xoá → danh sách rỗng. `limit`/`cursor`/`status`/`set_id` sai → 422 `validation_error`. "
        "Thiếu/sai token → 401 `token_invalid`; thiếu quyền → 403 `permission_denied`."
    ),
)
async def list_jobs(
    status: JobStatus | None = Query(None),
    set_id: int | None = Query(None, gt=0, le=BIGINT_MAX),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    current: CurrentUser = Depends(AI_USE),
    db: AsyncSession = Depends(get_db),
) -> Page[VideoJobResponse]:
    """Job video của user đang đăng nhập, phân trang cursor."""
    query = VideoJobListQuery(status=status, set_id=set_id, limit=limit, cursor=cursor)
    return await video_job_service.list_jobs(db, current.id, query)
