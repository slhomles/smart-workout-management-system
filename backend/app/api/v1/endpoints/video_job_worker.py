"""Endpoint worker video /ai/video-jobs/... (06-ai-contracts §3.2): worker AI nhận job và báo kết quả.

Xác thực bằng header `X-Worker-Token` (06 §3.1) cho cả router, không dùng JWT/RBAC của user, nên tách
khỏi `video_jobs.py` dù cùng prefix.
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import verify_worker_token
from app.schemas.base import ERROR_RESPONSES
from app.schemas.video_job import ClaimedVideoJobResponse, ClaimVideoJobRequest
from app.services import video_job_worker_service

router = APIRouter(prefix="/ai/video-jobs", tags=["AI"], dependencies=[Depends(verify_worker_token)])

WORKER = "Chỉ dành cho worker AI, header `X-Worker-Token` (= AI_WORKER_TOKEN). Sai/thiếu → 401 `unauthorized`."


@router.post(
    "/claim",
    response_model=ClaimedVideoJobResponse,
    status_code=200,
    responses={**ERROR_RESPONSES, 204: {"description": "Hết job trong hàng đợi (không body)"}},
    summary="Worker nhận job phân tích video tiếp theo trong hàng đợi",
    description=(
        WORKER + " Lấy job `queued` còn lượt thử, ưu tiên cao nhất rồi cũ nhất (`FOR UPDATE SKIP LOCKED`), "
        "bỏ qua job của buổi đã xoá; chuyển sang `processing`, tăng `attempt_count`, ghi `worker_id`. "
        "Trả 200 kèm ngữ cảnh job, hoặc 204 không body khi hết job. "
        "Body sai (`worker_id` thiếu, rỗng, dài hơn 100 ký tự, không phải chuỗi) → 422 `validation_error`."
    ),
)
async def claim_job(
    body: ClaimVideoJobRequest,
    db: AsyncSession = Depends(get_db),
) -> ClaimedVideoJobResponse | Response:
    """Worker nhận job kế tiếp; hết job thì trả 204."""
    claimed = await video_job_worker_service.claim_next_job(db, body.worker_id)
    if claimed is None:
        return Response(status_code=204)
    return claimed
