"""Endpoint worker video /ai/video-jobs/... (06-ai-contracts §3.2): worker AI nhận job và báo kết quả.

Xác thực bằng header `X-Worker-Token` (06 §3.1) cho cả router, không dùng JWT/RBAC của user, nên tách
khỏi `video_jobs.py` dù cùng prefix.
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import verify_worker_token
from app.schemas.base import ERROR_RESPONSES, ErrorResponse
from app.schemas.video_job import (
    ClaimedVideoJobResponse,
    ClaimVideoJobRequest,
    VideoJobFailureRequest,
    VideoJobResponse,
)
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


@router.get(
    "/{job_id}/source-video",
    response_class=Response,
    responses={
        **ERROR_RESPONSES,
        200: {"content": {"video/mp4": {}}, "description": "Byte video gốc, Content-Type theo media_files.mime_type"},
        503: {"model": ErrorResponse, "description": "Kho lưu trữ không khả dụng"},
    },
    summary="Worker tải video gốc của job đang xử lý",
    description=(
        WORKER + " Chỉ khi job đang `processing`. Trả byte video gốc (không bọc JSON), `Content-Type` theo "
        "MIME của video. Lỗi: 404 `not_found` (job không có, buổi đã xoá, video gốc đã xoá hoặc không còn file); "
        "409 `conflict` (job không ở `processing`); 422 `validation_error` (`job_id` không phải UUID); "
        "503 `service_unavailable` (kho lưu trữ lỗi)."
    ),
)
async def get_source_video(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Response:
    """Trả byte video gốc của job cho worker."""
    data, mime = await video_job_worker_service.get_source_video(db, job_id)
    return Response(content=data, media_type=mime)


@router.post(
    "/{job_id}/result",
    response_model=VideoJobResponse,
    status_code=200,
    responses={**ERROR_RESPONSES, 503: {"model": ErrorResponse, "description": "Kho lưu trữ không khả dụng"}},
    summary="Worker gửi kết quả phân tích và video kết quả của job",
    description=(
        WORKER + " `multipart/form-data`: part `video` (MP4 kết quả đã vẽ khung xương, tối đa 200 MiB) và part "
        "`result` (chuỗi JSON `VideoJobWorkerResult`, không có `result_video_media_id`). Job `queued`/`processing` "
        "→ `completed`; backend lưu video vào kho, tạo `media_files` hệ thống, ghi kết quả phân tích và rep vào hiệp. "
        "Lỗi: 404 `not_found` (job không có, buổi đã xoá); 409 `conflict` (job đã completed/failed/cancelled); "
        "422 `validation_error` (thiếu part, `result` không phải JSON hợp lệ hoặc sai giá trị, `video` rỗng, quá lớn "
        "hoặc không phải MP4, `job_id` không phải UUID); 503 `service_unavailable` (kho lưu trữ lỗi)."
    ),
)
async def submit_result(
    job_id: uuid.UUID,
    video: UploadFile = File(..., description="Video kết quả MP4, 1 byte – 200 MiB"),
    result: str = Form(..., description="Chuỗi JSON VideoJobWorkerResult"),
    db: AsyncSession = Depends(get_db),
) -> VideoJobResponse:
    """Worker gửi kết quả phân tích kèm video kết quả."""
    return await video_job_worker_service.submit_result(db, job_id, video, result)


@router.post(
    "/{job_id}/failure",
    response_model=VideoJobResponse,
    status_code=200,
    responses=ERROR_RESPONSES,
    summary="Worker báo job phân tích video thất bại",
    description=(
        WORKER + " Job `queued`/`processing` → `failed` kèm `error_message` (thông báo ngắn, không stack trace); "
        "không đụng kết quả phân tích và hiệp tập. Response không chứa `error_message`, `worker_id`. "
        "Lỗi: 404 `not_found` (job không có, buổi đã xoá); 409 `conflict` (job đã completed/failed/cancelled); "
        "422 `validation_error` (`error_message` thiếu, rỗng, dài hơn 2000 ký tự; `job_id` không phải UUID)."
    ),
)
async def report_failure(
    job_id: uuid.UUID,
    body: VideoJobFailureRequest,
    db: AsyncSession = Depends(get_db),
) -> VideoJobResponse:
    """Worker báo lỗi xử lý job."""
    return await video_job_worker_service.submit_failure(db, job_id, body)
