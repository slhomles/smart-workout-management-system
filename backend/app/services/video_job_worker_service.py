"""
Nghiệp vụ route worker video `/ai/video-jobs/...` (06-ai-contracts §3): nhận job, tải video gốc,
báo kết quả hoặc lỗi.

Chuyển trạng thái job dùng lại `video_job_service.start_job`/`record_result`/`record_failure`;
module này không sửa `video_job_service`, chỉ thêm phần hàng đợi, đọc/ghi file và ngữ cảnh worker cần.
"""

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ServiceUnavailableError
from app.crud import video_job as crud
from app.models.enums import JobStatus
from app.schemas.base import ErrorDetail
from app.schemas.video_job import ClaimedVideoJobResponse, VideoJobFailureRequest, VideoJobResponse
from app.services import storage_service, video_job_service

logger = logging.getLogger(__name__)

# Giới hạn video kết quả worker gửi lên, chặn request làm đầy bộ nhớ/kho; hằng số tạm (spec §6 ý 6.5, Q6).
MAX_RESULT_VIDEO_BYTES = 200 * 1024 * 1024

# Job còn chờ kết quả; khớp `_lock_pending_job` của video_job_service (record_result/record_failure).
_PENDING_STATUSES = frozenset({JobStatus.QUEUED, JobStatus.PROCESSING})


async def claim_next_job(db: AsyncSession, worker_id: str) -> ClaimedVideoJobResponse | None:
    """Nhận job `queued` ưu tiên cao nhất rồi cũ nhất, chuyển `processing`; None nếu hàng đợi trống."""
    job_id = await crud.claim_next_job_id(db)
    if job_id is None:
        return None
    # start_job khoá lại dòng trong cùng transaction, kiểm lượt thử rồi commit (nhả khoá SKIP LOCKED).
    await video_job_service.start_job(db, job_id, worker_id)
    # Luôn có dòng: câu claim đã đòi buổi chưa xoá (EXISTS trên view) và FK media nguồn NOT NULL.
    context = await crud.get_claim_context(db, job_id)
    return ClaimedVideoJobResponse.model_validate(context)


async def _get_job(db: AsyncSession, job_id: uuid.UUID) -> Any:
    """Job theo id (không lọc chủ); không có hoặc buổi đã xoá mềm → 404 `not_found` (06 §3.2)."""
    job = await crud.get_worker_job(db, job_id)
    if job is None:
        raise NotFoundError()
    return job


async def _pending_job(db: AsyncSession, job_id: uuid.UUID) -> Any:
    """Job còn chờ kết quả (`queued`/`processing`); không có → 404, đã kết thúc → 409 `conflict`."""
    job = await _get_job(db, job_id)
    if job["status"] not in _PENDING_STATUSES:
        raise ConflictError()
    return job


async def _read_source(job_id: uuid.UUID, bucket: str, object_key: str) -> bytes:
    """Đọc file video gốc từ kho; kho lỗi → 503 (không lộ chi tiết), file không còn → 404."""
    try:
        data = await storage_service.read_object(bucket, object_key)
    except Exception as exc:
        logger.exception("video worker: không đọc được video gốc job_id=%s", job_id)
        raise ServiceUnavailableError(
            "Kho lưu trữ video tạm thời không khả dụng",
            [ErrorDetail(field="storage", message="Không đọc được video gốc từ kho lưu trữ", code="down")],
        ) from exc
    if data is None:
        raise NotFoundError()
    return data


async def get_source_video(db: AsyncSession, job_id: uuid.UUID) -> tuple[bytes, str]:
    """Byte + MIME video gốc của job đang `processing` (06 §3.2).

    Thứ tự: job không có → 404; không ở `processing` → 409; media nguồn đã xoá/chưa sẵn sàng → 404;
    rồi mới đọc kho, nên các ca lỗi trên không chạm kho lưu trữ.
    """
    job = await _get_job(db, job_id)
    if job["status"] != JobStatus.PROCESSING:
        raise ConflictError()
    media = await crud.get_source_media(db, job["source_video_media_id"])
    if media is None:
        raise NotFoundError()
    data = await _read_source(job_id, media["bucket"], media["object_key"])
    return data, media["mime_type"]


async def submit_failure(db: AsyncSession, job_id: uuid.UUID, req: VideoJobFailureRequest) -> VideoJobResponse:
    """Worker báo lỗi: job `queued`/`processing` → `failed` kèm error_message; trả job đọc lại."""
    # Kiểm trước record_failure: record_failure khoá job theo id nên không biết buổi đã xoá mềm (phải 404).
    await _pending_job(db, job_id)
    await video_job_service.record_failure(db, job_id, req)
    return VideoJobResponse.model_validate(dict(await _get_job(db, job_id)))
