"""Truy vấn phân tích tư thế (schema `ai`). Không commit; không biết HTTP.

Ngữ cảnh hiệp (training.*) và mã lỗi (catalog.exercise_mistakes) chỉ ĐỌC bằng text(), không import
crud/model của module khác (spec posture-correction §6 ý 3). Số lỗi lấy từ view, không đếm lại.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import PoseAnalysis, PostureIssue

# Dùng chung cho đọc theo id và danh sách: view cung cấp ngữ cảnh + số lỗi, bảng gốc cung cấp
# các cột view không có (feedback_summary, keypoints_media_id, created_at).
DETAILS_SELECT = """
SELECT d.pose_analysis_id AS id, d.set_id, d.session_id, d.exercise_id, d.exercise_name, d.mode,
       d.model_name, d.model_version, d.overall_score, d.correct_form_pct, d.detected_rep_count,
       pa.feedback_summary, pa.keypoints_media_id, d.video_job_status, d.result_video_media_id,
       d.issue_count, d.critical_issue_count, d.analyzed_at, pa.created_at
FROM ai.v_pose_analysis_details d
JOIN ai.pose_analyses pa ON pa.id = d.pose_analysis_id
WHERE d.user_id = :user_id
"""

_OWNED_SET_SQL = """
SELECT es.id AS set_id, s.id AS session_id, se.exercise_id, e.supports_ai_tracking
FROM training.exercise_sets es
JOIN training.session_exercises se ON se.id = es.session_exercise_id
JOIN training.workout_sessions s ON s.id = se.session_id
JOIN catalog.exercises e ON e.id = se.exercise_id
WHERE es.id = :set_id AND s.user_id = :user_id AND s.deleted_at IS NULL
"""


async def db_now(db: AsyncSession) -> datetime:
    """Giờ của DB (now() của transaction hiện tại)."""
    return await db.scalar(text("SELECT now()"))


async def get_owned_set_context(db: AsyncSession, user_id: uuid.UUID, set_id: int) -> Any | None:
    """Hiệp của user trong buổi chưa xoá mềm: set_id, session_id, exercise_id, supports_ai_tracking."""
    result = await db.execute(text(_OWNED_SET_SQL), {"set_id": set_id, "user_id": user_id})
    return result.mappings().first()


async def valid_mistake_ids(db: AsyncSession, exercise_id: int, ids: Sequence[int]) -> set[int]:
    """Các id trong `ids` là mã lỗi của đúng bài `exercise_id`."""
    if not ids:
        return set()
    sql = "SELECT id FROM catalog.exercise_mistakes WHERE exercise_id = :exercise_id AND id = ANY(:ids)"
    rows = await db.scalars(text(sql), {"exercise_id": exercise_id, "ids": list(ids)})
    return set(rows)


async def insert_analysis(db: AsyncSession, analysis: PoseAnalysis, issues: list[PostureIssue]) -> uuid.UUID:
    """Ghi phân tích rồi các lỗi của nó (flush, không commit); trả id phân tích."""
    db.add(analysis)
    await db.flush()
    for issue in issues:
        issue.pose_analysis_id = analysis.id
    db.add_all(issues)
    await db.flush()
    return analysis.id


async def get_analysis(db: AsyncSession, user_id: uuid.UUID, analysis_id: uuid.UUID) -> Any | None:
    """Một phân tích của user (đã lọc buổi xoá mềm qua view), chưa kèm lỗi."""
    sql = DETAILS_SELECT + " AND d.pose_analysis_id = :id"
    result = await db.execute(text(sql), {"user_id": user_id, "id": analysis_id})
    return result.mappings().first()


@dataclass(frozen=True)
class AnalysisListQuery:
    """Điều kiện danh sách đã kiểm tra ở service; `None` = không lọc theo field đó."""

    limit: int
    set_id: int | None = None
    exercise_id: int | None = None
    mode: str | None = None
    after: tuple[datetime, uuid.UUID] | None = None


# Danh sách trắng mệnh đề lọc: SQL cố định, giá trị luôn bind (không nối chuỗi giá trị người dùng).
_LIST_FILTERS = (
    ("set_id", " AND d.set_id = :set_id"),
    ("exercise_id", " AND d.exercise_id = :exercise_id"),
    ("mode", " AND d.mode = CAST(:mode AS ai.analysis_mode)"),
)


async def list_analyses(db: AsyncSession, user_id: uuid.UUID, query: AnalysisListQuery) -> list[Any]:
    """Phân tích của user (view đã ẩn buổi xoá mềm), keyset (created_at DESC, id DESC), tối đa `query.limit` dòng."""
    sql = DETAILS_SELECT
    params: dict[str, Any] = {"user_id": user_id, "limit": query.limit}
    for name, clause in _LIST_FILTERS:
        value = getattr(query, name)
        if value is not None:
            sql += clause
            params[name] = value
    if query.after is not None:
        sql += " AND (pa.created_at, pa.id) < (:c_created_at, :c_id)"
        params["c_created_at"], params["c_id"] = query.after
    sql += " ORDER BY pa.created_at DESC, pa.id DESC LIMIT :limit"
    result = await db.execute(text(sql), params)
    return list(result.mappings().all())


async def issues_of(db: AsyncSession, analysis_ids: Sequence[uuid.UUID]) -> list[Any]:
    """Lỗi của nhiều phân tích trong MỘT truy vấn, sắp (offset_ms, id) trong từng phân tích."""
    if not analysis_ids:
        return []
    sql = """
        SELECT id, pose_analysis_id, mistake_id, rep_no, offset_ms, frame_index, severity, measured_angle_deg
        FROM ai.posture_issues
        WHERE pose_analysis_id = ANY(:ids)
        ORDER BY pose_analysis_id, offset_ms, id
    """
    result = await db.execute(text(sql), {"ids": list(analysis_ids)})
    return list(result.mappings().all())
