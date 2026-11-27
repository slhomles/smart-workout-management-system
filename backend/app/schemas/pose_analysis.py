"""Schema Pydantic cho /ai/pose-analyses — kết quả phân tích tư thế (chức năng 5).
Giới hạn giá trị khớp CHECK và kiểu cột trong 07_ai.sql (bigint/integer/smallint, numeric(5,2))."""

import uuid
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.models.enums import AnalysisMode, IssueSeverity, JobStatus

BIGINT_MAX = 9223372036854775807
INT_MAX = 2147483647
SMALLINT_MAX = 32767
MAX_ISSUES = 500


class CreatePostureIssueRequest(BaseModel):
    """Một lỗi tư thế thiết bị phát hiện; `mistake_id` phải thuộc đúng bài của hiệp."""

    mistake_id: int = Field(..., gt=0, le=INT_MAX, description="catalog.exercise_mistakes.id")
    rep_no: int | None = Field(None, ge=1, le=SMALLINT_MAX)
    offset_ms: int = Field(..., ge=0, le=INT_MAX, description="Thời điểm lỗi tính từ đầu hiệp (ms)")
    frame_index: int | None = Field(None, ge=0, le=INT_MAX)
    severity: IssueSeverity = IssueSeverity.WARNING
    measured_angle_deg: float | None = Field(None, ge=0, le=360, description="Góc khớp đo được (độ)")


class CreatePoseAnalysisRequest(BaseModel):
    """Kết quả phân tích realtime (MediaPipe trên thiết bị) gửi lên khi user bấm "Dừng"."""

    set_id: int = Field(..., gt=0, le=BIGINT_MAX, description="training.exercise_sets.id của chính user")
    model_name: str = Field(..., min_length=1, max_length=50)
    model_version: str = Field(..., min_length=1, max_length=50)
    correct_form_pct: float = Field(..., ge=0, le=100, description="Tỷ lệ % đúng form (0–100)")
    overall_score: float | None = Field(None, ge=0, le=100, description="Điểm kỹ thuật (0–100)")
    detected_rep_count: int | None = Field(None, ge=0, le=SMALLINT_MAX)
    feedback_summary: str | None = Field(None, max_length=2000)
    analyzed_at: AwareDatetime | None = Field(None, description="Vắng mặt → giờ server; tối đa giờ server + 5 phút")
    issues: list[CreatePostureIssueRequest] = Field(default_factory=list, max_length=MAX_ISSUES)

    # model_name/model_version là tên cột DB; tắt vùng tên "model_" mà Pydantic dành riêng.
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "set_id": 1,
                "model_name": "mediapipe_blazepose",
                "model_version": "0.10.14",
                "overall_score": 82.5,
                "correct_form_pct": 76.0,
                "detected_rep_count": 8,
                "feedback_summary": "Lưng dưới bị cong ở rep 3",
                "analyzed_at": "2026-11-26T03:20:41Z",
                "issues": [
                    {"mistake_id": 1, "rep_no": 3, "offset_ms": 12500, "severity": "critical", "measured_angle_deg": 142.5}
                ],
            }
        },
    )


class PoseAnalysisFilter(BaseModel):
    """Query của GET /ai/pose-analyses: bộ lọc + phân trang cursor (Claude_api_respone §5).

    Cận trên của id khớp kiểu cột (bigint/integer) để giá trị tràn trả 422 thay vì lỗi bind 500.
    """

    set_id: int | None = Field(None, gt=0, le=BIGINT_MAX, description="training.exercise_sets.id")
    exercise_id: int | None = Field(None, gt=0, le=INT_MAX, description="catalog.exercises.id")
    mode: AnalysisMode | None = Field(None, description="realtime_edge | video_server")
    limit: int = Field(20, ge=1, le=100)
    cursor: str | None = Field(None, description="`next_cursor` của trang trước")


class PostureIssueSchema(BaseModel):
    """Một dòng ai.posture_issues."""

    id: int
    mistake_id: int
    rep_no: int | None
    offset_ms: int
    frame_index: int | None
    severity: IssueSeverity
    measured_angle_deg: float | None

    model_config = ConfigDict(from_attributes=True)


class PoseAnalysisResponse(BaseModel):
    """Một phân tích tư thế kèm ngữ cảnh hiệp/bài/buổi (ai.v_pose_analysis_details) và các lỗi."""

    id: uuid.UUID
    set_id: int
    session_id: uuid.UUID
    exercise_id: int
    exercise_name: str
    mode: AnalysisMode
    model_name: str
    model_version: str
    overall_score: float | None
    correct_form_pct: float | None
    detected_rep_count: int | None
    feedback_summary: str | None
    keypoints_media_id: uuid.UUID | None
    video_job_status: JobStatus | None
    result_video_media_id: uuid.UUID | None
    issue_count: int
    critical_issue_count: int
    analyzed_at: datetime | None
    created_at: datetime
    issues: list[PostureIssueSchema]

    model_config = ConfigDict(
        from_attributes=True,
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "id": "3f1c2a8e-5b7d-4e2a-9c1f-0a6b8d4e2f10",
                "set_id": 1,
                "session_id": "9a4e7c21-3d5b-4f8a-b6c2-1e0d9f7a5b34",
                "exercise_id": 30,
                "exercise_name": "Squat với tạ đòn",
                "mode": "realtime_edge",
                "model_name": "mediapipe_blazepose",
                "model_version": "0.10.14",
                "overall_score": 82.5,
                "correct_form_pct": 76.0,
                "detected_rep_count": 8,
                "feedback_summary": "Lưng dưới bị cong ở rep 3 (SQUAT_BACK_ROUNDING)",
                "keypoints_media_id": None,
                "video_job_status": None,
                "result_video_media_id": None,
                "issue_count": 1,
                "critical_issue_count": 1,
                "analyzed_at": "2026-11-26T03:20:41Z",
                "created_at": "2026-11-26T03:20:42Z",
                "issues": [
                    {"id": 1, "mistake_id": 1, "rep_no": 3, "offset_ms": 12500, "frame_index": None,
                     "severity": "critical", "measured_angle_deg": 142.5}
                ],
            }
        },
    )
