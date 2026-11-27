"""
Nghiệp vụ /ai/video-jobs (chức năng 6, luồng video 1B): tạo job phân tích video cho một hiệp.

Hàng đợi chính là các dòng `ai.video_analysis_jobs` ở trạng thái `queued`; worker tự lấy job
(`FOR UPDATE SKIP LOCKED`, design-overview §5), nên service không gọi HTTP/Redis để đẩy job.
Hiệp tập chỉ đọc/ghi qua `workout_ai_service` của module Training (doc 05 §6.3).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, DataValidationError, NotFoundError
from app.crud import body as body_crud
from app.crud import video_job as crud
from app.models.ai import PoseAnalysis, VideoAnalysisJob
from app.models.enums import JobStatus, LogSource
from app.schemas.base import ErrorDetail, Page, build_page, decode_keyset_cursor
from app.schemas.video_job import (
    CreateVideoJobRequest,
    VideoJobFailureRequest,
    VideoJobListQuery,
    VideoJobResponse,
    VideoJobResultRequest,
)
from app.services import workout_ai_service

# Cột model_* NOT NULL nên cần giá trị khi job còn chờ; worker ghi đè khi báo kết quả (spec §6 ý 6, Q8).
DEFAULT_MODEL_NAME = "yolov8_pose"
DEFAULT_MODEL_VERSION = "8.2.0"

# Khớp cột ai.video_analysis_jobs.worker_id varchar(100).
WORKER_ID_MAX_LENGTH = 100
_PENDING_STATUSES = frozenset({JobStatus.QUEUED, JobStatus.PROCESSING})


def _job_response(row: Any) -> VideoJobResponse:
    return VideoJobResponse.model_validate(dict(row))


def _unsupported_set_error() -> DataValidationError:
    return DataValidationError(
        [ErrorDetail(field="set_id", message="Bài tập của hiệp này chưa hỗ trợ AI đếm rep", code="ai_tracking_not_supported")]
    )


def _invalid_source_video_error() -> DataValidationError:
    # Cùng một message cho mọi lý do, để không lộ video của user khác.
    return DataValidationError(
        [ErrorDetail(
            field="source_video_media_id",
            message="Video không tồn tại hoặc chưa sẵn sàng để phân tích",
            code="invalid_media",
        )]
    )


async def _ensure_own_video(db: AsyncSession, user_id: uuid.UUID, media_id: uuid.UUID) -> None:
    video = await crud.get_available_video(db, media_id)
    if video is None or video["uploaded_by_user_id"] != user_id:
        raise _invalid_source_video_error()


async def create_job(db: AsyncSession, user_id: uuid.UUID, req: CreateVideoJobRequest) -> VideoJobResponse:
    """Tạo pose_analyses (video_server) + job queued cho hiệp của user, trong một transaction."""
    context = await workout_ai_service.get_owned_set_context(db, user_id, req.set_id)
    if not context.supports_ai_tracking:
        raise _unsupported_set_error()
    await _ensure_own_video(db, user_id, req.source_video_media_id)

    analysis = await crud.create_pose_analysis(db, context.set_id, DEFAULT_MODEL_NAME, DEFAULT_MODEL_VERSION)
    job = await crud.create_job(db, analysis.id, req.source_video_media_id)
    await db.commit()

    # Đọc lại qua view để có ngữ cảnh hiệp/bài và các giá trị mặc định do DB sinh (queued_at, status...).
    return _job_response(await crud.get_job(db, user_id, job.id))


def _job_cursor(row: Any) -> dict[str, Any]:
    # isoformat() giữ microsecond + múi giờ, khớp định dạng decode_keyset_cursor đọc lại.
    return {"created_at": row["created_at"].isoformat(), "id": str(row["id"])}


async def list_jobs(db: AsyncSession, user_id: uuid.UUID, query: VideoJobListQuery) -> Page[VideoJobResponse]:
    """Trang job video của user (mới nhất trước), lọc theo trạng thái/hiệp; cursor hỏng → 422."""
    after = decode_keyset_cursor(query.cursor, "created_at")
    rows = await crud.list_jobs(db, user_id, query, after)
    return build_page(rows, query.limit, _job_response, _job_cursor)


# --- Service cho worker (chưa có route HTTP, spec §2.2, Q1) ---
async def _lock_existing_job(db: AsyncSession, job_id: uuid.UUID) -> VideoAnalysisJob:
    job = await crud.lock_job(db, job_id)
    if job is None:
        raise NotFoundError()
    return job


async def _lock_pending_job(db: AsyncSession, job_id: uuid.UUID) -> VideoAnalysisJob:
    """Khoá job còn chờ kết quả (`queued`/`processing`); không có → 404, đã kết thúc → 409."""
    job = await _lock_existing_job(db, job_id)
    if job.status not in _PENDING_STATUSES:
        raise ConflictError()
    return job


def _ensure_valid_worker_id(worker_id: str) -> None:
    if not 1 <= len(worker_id) <= WORKER_ID_MAX_LENGTH:
        raise DataValidationError(
            [ErrorDetail(
                field="worker_id",
                message=f"worker_id phải dài 1..{WORKER_ID_MAX_LENGTH} ký tự",
                code="invalid_length",
            )]
        )


async def start_job(db: AsyncSession, job_id: uuid.UUID, worker_id: str) -> None:
    """Worker nhận job: `queued` → `processing`, tăng attempt_count, ghi worker_id và started_at."""
    _ensure_valid_worker_id(worker_id)
    job = await _lock_existing_job(db, job_id)
    # Hết lượt thử thì không cho chạy lại, nếu không sẽ vi phạm ck_video_analysis_jobs_attempts.
    if job.status != JobStatus.QUEUED or job.attempt_count >= job.max_attempts:
        raise ConflictError()
    job.status = JobStatus.PROCESSING
    job.started_at = await body_crud.db_now(db)
    job.attempt_count += 1
    job.worker_id = worker_id
    await db.commit()


def _invalid_result_video_error() -> DataValidationError:
    # Cùng một message cho mọi lý do (không có, đã xoá, chưa sẵn sàng, không phải video, trùng video gốc).
    return DataValidationError(
        [ErrorDetail(
            field="result_video_media_id",
            message="Video kết quả không tồn tại, chưa sẵn sàng hoặc trùng video gốc",
            code="invalid_media",
        )]
    )


async def _ensure_result_video(db: AsyncSession, media_id: uuid.UUID, source_media_id: uuid.UUID) -> None:
    # Không kiểm người upload: video kết quả do hệ thống sinh có uploaded_by_user_id NULL.
    # Khác video gốc để thoả ck_video_analysis_jobs_distinct_media.
    if media_id == source_media_id or await crud.get_available_video(db, media_id) is None:
        raise _invalid_result_video_error()


def _apply_analysis_result(analysis: PoseAnalysis, req: VideoJobResultRequest, now: datetime) -> None:
    analysis.model_name = req.model_name
    analysis.model_version = req.model_version
    analysis.overall_score = req.overall_score
    analysis.correct_form_pct = req.correct_form_pct
    analysis.feedback_summary = req.feedback_summary
    analysis.detected_rep_count = len(req.rep_events)
    analysis.analyzed_at = now


async def record_result(db: AsyncSession, job_id: uuid.UUID, req: VideoJobResultRequest) -> None:
    """Worker báo kết quả: job còn chờ → `completed`, ghi pose_analyses và rep vào hiệp; commit một lần.

    Không có job → 404 `not_found`; job đã kết thúc → 409 `conflict`; video kết quả không dùng được
    → 422 field `result_video_media_id`. Mọi kiểm tra chạy trước lệnh ghi đầu tiên.
    """
    job = await _lock_pending_job(db, job_id)
    await _ensure_result_video(db, req.result_video_media_id, job.source_video_media_id)
    # Một mốc thời gian chung cho analyzed_at/started_at/finished_at.
    now = await body_crud.db_now(db)
    analysis = await crud.get_pose_analysis(db, job.pose_analysis_id)
    _apply_analysis_result(analysis, req, now)
    await workout_ai_service.apply_ai_rep_events(db, analysis.set_id, req.rep_events, LogSource.AI_VIDEO)
    job.status = JobStatus.COMPLETED
    job.result_video_media_id = req.result_video_media_id
    # Job nhận kết quả khi worker chưa gọi start vẫn cần started_at để thoả ck_video_analysis_jobs_times.
    job.started_at = job.started_at or now
    job.finished_at = now
    await db.commit()


async def record_failure(db: AsyncSession, job_id: uuid.UUID, req: VideoJobFailureRequest) -> None:
    """Worker báo lỗi: job còn chờ → `failed` kèm error_message; không đụng pose_analyses và hiệp."""
    job = await _lock_pending_job(db, job_id)
    now = await body_crud.db_now(db)
    job.status = JobStatus.FAILED
    job.error_message = req.error_message
    # Job lỗi trước khi worker start vẫn cần started_at để thoả ck_video_analysis_jobs_times.
    job.started_at = job.started_at or now
    job.finished_at = now
    await db.commit()
