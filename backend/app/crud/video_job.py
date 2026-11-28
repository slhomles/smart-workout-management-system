"""Truy vấn job phân tích video (ai.video_analysis_jobs + ai.pose_analyses), hàng đợi worker và media video.

`media.media_files` truy cập bằng `text()` vì module Gallery chưa có service công khai cho file
hệ thống (spec be-video-worker-api §6 ý 6, Q3).
Ngữ cảnh hiệp/buổi/bài lấy từ view `ai.v_pose_analysis_details` (đã lọc buổi xoá mềm).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import PoseAnalysis, VideoAnalysisJob
from app.models.enums import AnalysisMode
from app.schemas.video_job import VideoJobListQuery

_AVAILABLE_VIDEO_SQL = """
SELECT id, uploaded_by_user_id
FROM media.media_files
WHERE id = :id AND deleted_at IS NULL AND status = 'available' AND mime_type LIKE 'video/%'
"""

# Cột + JOIN chung của job; JOIN view nên job thuộc buổi đã xoá mềm không có dòng.
_JOB_BASE_SELECT = """
SELECT j.id, j.pose_analysis_id, d.set_id, d.session_id, d.exercise_id, d.exercise_name, j.status,
       j.source_video_media_id, j.result_video_media_id, d.model_name, d.model_version,
       d.overall_score, d.correct_form_pct, d.detected_rep_count, pa.feedback_summary,
       j.queued_at, j.started_at, j.finished_at, d.analyzed_at, j.created_at
FROM ai.video_analysis_jobs j
JOIN ai.v_pose_analysis_details d ON d.pose_analysis_id = j.pose_analysis_id
JOIN ai.pose_analyses pa ON pa.id = j.pose_analysis_id
"""

# SELECT dùng chung cho đọc một job và danh sách job của user (lọc thêm bằng `AND ...`).
JOB_SELECT = _JOB_BASE_SELECT + "WHERE d.user_id = :user_id\n"

_SOURCE_MEDIA_SQL = """
SELECT bucket, object_key, mime_type
FROM media.media_files
WHERE id = :id AND deleted_at IS NULL AND status = 'available'
"""

# Job queued còn lượt thử, buổi chưa xoá mềm; ưu tiên cao nhất rồi cũ nhất (dùng ix_video_analysis_jobs_queue).
# SKIP LOCKED để nhiều worker cùng claim không chờ nhau; j.id làm khoá phụ cho thứ tự tất định.
_CLAIM_NEXT_SQL = """
SELECT j.id
FROM ai.video_analysis_jobs j
WHERE j.status = 'queued'
  AND j.attempt_count < j.max_attempts
  AND EXISTS (SELECT 1 FROM ai.v_pose_analysis_details d WHERE d.pose_analysis_id = j.pose_analysis_id)
ORDER BY j.priority DESC, j.queued_at, j.id
LIMIT 1
FOR UPDATE OF j SKIP LOCKED
"""

_CLAIM_CONTEXT_SQL = """
SELECT j.id AS job_id, d.set_id, d.exercise_id, e.slug AS exercise_slug, j.attempt_count,
       m.mime_type AS source_video_content_type
FROM ai.video_analysis_jobs j
JOIN ai.v_pose_analysis_details d ON d.pose_analysis_id = j.pose_analysis_id
JOIN catalog.exercises e ON e.id = d.exercise_id
JOIN media.media_files m ON m.id = j.source_video_media_id
WHERE j.id = :job_id
"""


async def get_available_video(db: AsyncSession, media_id: uuid.UUID) -> Any | None:
    """Video dùng được (chưa xoá, `available`, MIME `video/*`) kèm người upload; None nếu không có."""
    return (await db.execute(text(_AVAILABLE_VIDEO_SQL), {"id": media_id})).mappings().first()


async def create_pose_analysis(
    db: AsyncSession, set_id: int, model_name: str, model_version: str
) -> PoseAnalysis:
    """Thêm phân tích `video_server` đang chờ (analyzed_at NULL); flush để có id, không commit."""
    analysis = PoseAnalysis(
        set_id=set_id, mode=AnalysisMode.VIDEO_SERVER, model_name=model_name, model_version=model_version
    )
    db.add(analysis)
    await db.flush()
    return analysis


async def create_job(
    db: AsyncSession, pose_analysis_id: uuid.UUID, source_video_media_id: uuid.UUID
) -> VideoAnalysisJob:
    """Thêm job (status/priority/attempt theo mặc định DB: queued, 5, 0); flush để có id, không commit."""
    job = VideoAnalysisJob(pose_analysis_id=pose_analysis_id, source_video_media_id=source_video_media_id)
    db.add(job)
    await db.flush()
    return job


async def lock_job(db: AsyncSession, job_id: uuid.UUID) -> VideoAnalysisJob | None:
    """Khoá dòng job (`SELECT … FOR UPDATE`) cho worker chuyển trạng thái; None nếu không có."""
    # populate_existing: object job có thể còn trong identity map với giá trị cũ (expire_on_commit=False),
    # phải nạp lại đúng dòng vừa khoá thì kiểm tra trạng thái/attempt mới đúng.
    stmt = (
        select(VideoAnalysisJob)
        .where(VideoAnalysisJob.id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return await db.scalar(stmt)


async def get_pose_analysis(db: AsyncSession, analysis_id: uuid.UUID) -> PoseAnalysis:
    """Phân tích của một job; luôn có vì FK NOT NULL video_analysis_jobs → pose_analyses (CASCADE)."""
    # populate_existing: object có thể còn trong identity map từ lúc tạo job (expire_on_commit=False).
    stmt = select(PoseAnalysis).where(PoseAnalysis.id == analysis_id).execution_options(populate_existing=True)
    return (await db.execute(stmt)).scalar_one()


async def get_job(db: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID) -> Any | None:
    """Một job của user kèm ngữ cảnh hiệp/bài; None nếu không có hoặc buổi đã xoá mềm."""
    sql = JOB_SELECT + " AND j.id = :job_id"
    return (await db.execute(text(sql), {"user_id": user_id, "job_id": job_id})).mappings().first()


async def list_jobs(
    db: AsyncSession, user_id: uuid.UUID, query: VideoJobListQuery, after: tuple[datetime, uuid.UUID] | None
) -> list[Any]:
    """Job của user, mới nhất trước (created_at DESC, id DESC), sau vị trí keyset `after`.

    Lấy `query.limit + 1` dòng để tầng trên biết còn trang sau mà không cần COUNT(*).
    """
    sql = JOB_SELECT
    params: dict[str, Any] = {"user_id": user_id, "limit": query.limit + 1}
    if query.status is not None:
        sql += " AND j.status = CAST(:status AS util.job_status)"
        params["status"] = query.status.value
    if query.set_id is not None:
        sql += " AND d.set_id = :set_id"
        params["set_id"] = query.set_id
    if after is not None:
        # So sánh cả tuple: các job tạo trong cùng transaction có thể trùng created_at.
        sql += " AND (j.created_at, j.id) < (:after_created_at, :after_id)"
        params["after_created_at"], params["after_id"] = after
    sql += " ORDER BY j.created_at DESC, j.id DESC LIMIT :limit"
    return list((await db.execute(text(sql), params)).mappings().all())


async def claim_next_job_id(db: AsyncSession) -> uuid.UUID | None:
    """Khoá và trả id job kế tiếp worker nên nhận (FOR UPDATE SKIP LOCKED); None nếu hàng đợi trống."""
    return await db.scalar(text(_CLAIM_NEXT_SQL))


async def get_claim_context(db: AsyncSession, job_id: uuid.UUID) -> Any | None:
    """Ngữ cảnh worker cần sau khi claim: hiệp, bài (id, slug), số lần thử, MIME video gốc; None nếu không có."""
    return (await db.execute(text(_CLAIM_CONTEXT_SQL), {"job_id": job_id})).mappings().first()


async def get_worker_job(db: AsyncSession, job_id: uuid.UUID) -> Any | None:
    """Một job bất kể chủ sở hữu (worker không có user); None nếu không có hoặc buổi đã xoá mềm."""
    sql = _JOB_BASE_SELECT + " WHERE j.id = :job_id"
    return (await db.execute(text(sql), {"job_id": job_id})).mappings().first()


async def get_source_media(db: AsyncSession, media_id: uuid.UUID) -> Any | None:
    """Vị trí kho + MIME của video gốc còn dùng được (chưa xoá, `available`); None nếu không có."""
    return (await db.execute(text(_SOURCE_MEDIA_SQL), {"id": media_id})).mappings().first()
