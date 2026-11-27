"""
Nghiệp vụ /ai/pose-analyses (chức năng 5, Option 1A): lưu kết quả phân tích tư thế realtime do
thiết bị gửi lên. Module không chạy mô hình AI và không gọi ai-services (spec §6 ý 2).
Không ghi bảng training.* (spec §6 ý 5).
"""

import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DataValidationError, NotFoundError
from app.crud import pose_analysis as crud
from app.models.ai import PoseAnalysis, PostureIssue
from app.models.enums import AnalysisMode
from app.schemas.base import ErrorDetail
from app.schemas.pose_analysis import (
    CreatePoseAnalysisRequest,
    CreatePostureIssueRequest,
    PoseAnalysisResponse,
    PostureIssueSchema,
)

# Một message cho "không tồn tại", "của user khác" và "buổi đã xoá mềm": không lộ sự tồn tại (doc 04 §2.4).
_SET_NOT_FOUND = ("exercise_set_not_found", "Không tìm thấy hiệp tập")
# Cho phép lệch đồng hồ thiết bị so với server.
_CLOCK_SKEW = timedelta(minutes=5)


def _invalid(field: str, message: str, code: str) -> DataValidationError:
    return DataValidationError([ErrorDetail(field=field, message=message, code=code)])


# --- Chuyển đổi ---
async def to_responses(db: AsyncSession, rows: Sequence[Any]) -> list[PoseAnalysisResponse]:
    """Ghép các dòng view với lỗi của chúng (một truy vấn cho mọi dòng, không N+1)."""
    issues: dict[uuid.UUID, list[PostureIssueSchema]] = {row["id"]: [] for row in rows}
    for issue in await crud.issues_of(db, list(issues)):
        issues[issue["pose_analysis_id"]].append(PostureIssueSchema.model_validate(dict(issue)))
    return [PoseAnalysisResponse(**row, issues=issues[row["id"]]) for row in rows]


# --- Kiểm tra đầu vào ---
async def _resolve_analyzed_at(db: AsyncSession, analyzed_at: datetime | None) -> datetime:
    now = await crud.db_now(db)
    if analyzed_at is None:
        return now
    if analyzed_at > now + _CLOCK_SKEW:
        raise _invalid("analyzed_at", "Thời điểm phân tích không được ở tương lai", "value_error")
    return analyzed_at


async def _owned_ai_set(db: AsyncSession, user_id: uuid.UUID, set_id: int) -> Any:
    context = await crud.get_owned_set_context(db, user_id, set_id)
    if context is None:
        raise NotFoundError(*_SET_NOT_FOUND)
    if not context["supports_ai_tracking"]:
        raise _invalid("set_id", "Bài tập của hiệp này không hỗ trợ phân tích AI", "value_error")
    return context


async def _ensure_mistakes_match(db: AsyncSession, exercise_id: int, issues: list[CreatePostureIssueRequest]) -> None:
    # Kiểm tra trước khi insert: để trigger trg_posture_issues_exercise_match chặn thì lỗi không có field.
    valid = await crud.valid_mistake_ids(db, exercise_id, [i.mistake_id for i in issues])
    for index, issue in enumerate(issues):
        if issue.mistake_id not in valid:
            raise _invalid(f"issues.{index}.mistake_id", "Mã lỗi không thuộc bài tập của hiệp", "invalid_reference")


# --- Ghi ---
def _build_analysis(body: CreatePoseAnalysisRequest, analyzed_at: datetime) -> PoseAnalysis:
    return PoseAnalysis(
        set_id=body.set_id,
        mode=AnalysisMode.REALTIME_EDGE,
        model_name=body.model_name,
        model_version=body.model_version,
        overall_score=body.overall_score,
        correct_form_pct=body.correct_form_pct,
        detected_rep_count=body.detected_rep_count,
        feedback_summary=body.feedback_summary,
        analyzed_at=analyzed_at,
    )


async def create_analysis(
    db: AsyncSession, user_id: uuid.UUID, body: CreatePoseAnalysisRequest
) -> PoseAnalysisResponse:
    """Lưu một phân tích realtime kèm các lỗi trong một transaction (spec §6 ý 5)."""
    analyzed_at = await _resolve_analyzed_at(db, body.analyzed_at)
    context = await _owned_ai_set(db, user_id, body.set_id)
    await _ensure_mistakes_match(db, context["exercise_id"], body.issues)
    issues = [PostureIssue(**issue.model_dump()) for issue in body.issues]
    analysis_id = await crud.insert_analysis(db, _build_analysis(body, analyzed_at), issues)
    await db.commit()
    row = await crud.get_analysis(db, user_id, analysis_id)
    if row is None:  # view lọc cùng điều kiện với _owned_ai_set; chỉ xảy ra nếu buổi vừa bị xoá mềm
        raise NotFoundError(*_SET_NOT_FOUND)
    return (await to_responses(db, [row]))[0]
