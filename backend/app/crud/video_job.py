"""Truy vấn job phân tích video (ai.video_analysis_jobs + ai.pose_analyses) và đọc media video.

`media.media_files` chỉ đọc bằng `text()` vì module Gallery chưa có service.
Ngữ cảnh hiệp/buổi/bài lấy từ view `ai.v_pose_analysis_details` (đã lọc buổi xoá mềm).
"""

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import PoseAnalysis, VideoAnalysisJob
from app.models.enums import AnalysisMode

_AVAILABLE_VIDEO_SQL = """
SELECT id, uploaded_by_user_id
FROM media.media_files
WHERE id = :id AND deleted_at IS NULL AND status = 'available' AND mime_type LIKE 'video/%'
"""

# SELECT dùng chung cho đọc một job và danh sách job của user (lọc thêm bằng `AND ...`).
JOB_SELECT = """
SELECT j.id, j.pose_analysis_id, d.set_id, d.session_id, d.exercise_id, d.exercise_name, j.status,
       j.source_video_media_id, j.result_video_media_id, d.model_name, d.model_version,
       d.overall_score, d.correct_form_pct, d.detected_rep_count, pa.feedback_summary,
       j.queued_at, j.started_at, j.finished_at, d.analyzed_at, j.created_at
FROM ai.video_analysis_jobs j
JOIN ai.v_pose_analysis_details d ON d.pose_analysis_id = j.pose_analysis_id
JOIN ai.pose_analyses pa ON pa.id = j.pose_analysis_id
WHERE d.user_id = :user_id
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


async def get_job(db: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID) -> Any | None:
    """Một job của user kèm ngữ cảnh hiệp/bài; None nếu không có hoặc buổi đã xoá mềm."""
    sql = JOB_SELECT + " AND j.id = :job_id"
    return (await db.execute(text(sql), {"user_id": user_id, "job_id": job_id})).mappings().first()
