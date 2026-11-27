"""Schema Pydantic cho /ai/video-jobs — job phân tích video (1B) và kết quả worker gửi về.
Giới hạn giá trị khớp cột/CHECK trong 07_ai.sql."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import JobStatus
from app.schemas.workout import RepEventInput

BIGINT_MAX = 9223372036854775807
_SAMPLE_JOB_ID = "8f0c2a4e-6b1d-4c3a-9e57-2d4b6f8a1c03"
_SAMPLE_POSE_ANALYSIS_ID = "3b9e1f70-52c4-4d8a-a6e2-7c1f0b5d9e48"
_SAMPLE_SESSION_ID = "c41d7e2a-9f35-4b60-8e1c-5a2d3f4b6c71"
_SAMPLE_SOURCE_VIDEO_ID = "e7a2c9d1-3f48-4b5e-9c06-1d2e3f4a5b6c"
_SAMPLE_RESULT_VIDEO_ID = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"


class CreateVideoJobRequest(BaseModel):
    """Gửi video của một hiệp để AI phân tích bất đồng bộ."""

    set_id: int = Field(..., gt=0, le=BIGINT_MAX, description="Hiệp tập của chính user (training.exercise_sets.id)")
    source_video_media_id: uuid.UUID = Field(..., description="Video gốc đã upload (media.media_files.id)")

    model_config = ConfigDict(
        json_schema_extra={"example": {"set_id": 1024, "source_video_media_id": _SAMPLE_SOURCE_VIDEO_ID}}
    )


class VideoJobResultRequest(BaseModel):
    """Kết quả worker gửi về khi phân tích video xong."""

    model_name: str = Field(..., min_length=1, max_length=50)
    model_version: str = Field(..., min_length=1, max_length=50)
    result_video_media_id: uuid.UUID = Field(..., description="Video kết quả (đã vẽ khung xương) do hệ thống sinh")
    overall_score: float | None = Field(None, ge=0, le=100)
    correct_form_pct: float | None = Field(None, ge=0, le=100)
    feedback_summary: str | None = Field(None, max_length=2000)
    rep_events: list[RepEventInput] = Field(default_factory=list, max_length=1000)

    # field_validator (không phải model_validator) để `loc` của lỗi chỉ đúng `rep_events`.
    @field_validator("rep_events")
    @classmethod
    def _rep_no_continuous(cls, rep_events: list[RepEventInput]) -> list[RepEventInput]:
        numbers = sorted(rep.rep_no for rep in rep_events)
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("rep_no phải liên tục từ 1 và không trùng")
        return rep_events

    model_config = ConfigDict(
        # Field `model_name`/`model_version` đặt theo cột DB; tắt cảnh báo trùng tiền tố `model_` của Pydantic.
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "model_name": "yolov8_pose",
                "model_version": "8.2.1",
                "result_video_media_id": _SAMPLE_RESULT_VIDEO_ID,
                "overall_score": 85,
                "correct_form_pct": 90,
                "feedback_summary": "Tempo đều, hạ chậm 3 giây",
                "rep_events": [
                    {"rep_no": 1, "start_offset_ms": 0, "eccentric_ms": 3000, "pause_bottom_ms": 200,
                     "concentric_ms": 1000, "pause_top_ms": 300, "min_joint_angle_deg": 78.5,
                     "max_joint_angle_deg": 172.0, "is_full_rom": True},
                    {"rep_no": 2, "start_offset_ms": 4600, "eccentric_ms": 2900, "pause_bottom_ms": 100,
                     "concentric_ms": 1100, "pause_top_ms": 300, "min_joint_angle_deg": 80.0,
                     "max_joint_angle_deg": 171.0, "is_full_rom": True},
                ],
            }
        },
    )


class VideoJobFailureRequest(BaseModel):
    """Worker báo job phân tích video thất bại."""

    error_message: str = Field(..., min_length=1, max_length=2000)

    model_config = ConfigDict(json_schema_extra={"example": {"error_message": "Không giải mã được video H.265"}})


class VideoJobResponse(BaseModel):
    """Trạng thái job video kèm kết quả phân tích; không lộ thông tin nội bộ (worker, lỗi thô)."""

    id: uuid.UUID
    pose_analysis_id: uuid.UUID
    set_id: int
    session_id: uuid.UUID
    exercise_id: int
    exercise_name: str
    status: JobStatus
    source_video_media_id: uuid.UUID
    result_video_media_id: uuid.UUID | None
    model_name: str
    model_version: str
    overall_score: float | None
    correct_form_pct: float | None
    detected_rep_count: int | None
    feedback_summary: str | None
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    analyzed_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        # Field `model_name`/`model_version` đặt theo cột DB; tắt cảnh báo trùng tiền tố `model_` của Pydantic.
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "id": _SAMPLE_JOB_ID,
                "pose_analysis_id": _SAMPLE_POSE_ANALYSIS_ID,
                "set_id": 1024,
                "session_id": _SAMPLE_SESSION_ID,
                "exercise_id": 10,
                "exercise_name": "Barbell Back Squat",
                "status": "completed",
                "source_video_media_id": _SAMPLE_SOURCE_VIDEO_ID,
                "result_video_media_id": _SAMPLE_RESULT_VIDEO_ID,
                "model_name": "yolov8_pose",
                "model_version": "8.2.1",
                "overall_score": 85.0,
                "correct_form_pct": 90.0,
                "detected_rep_count": 3,
                "feedback_summary": "Tempo đều, hạ chậm 3 giây",
                "queued_at": "2026-11-26T03:20:41Z",
                "started_at": "2026-11-26T03:20:45Z",
                "finished_at": "2026-11-26T03:21:30Z",
                "analyzed_at": "2026-11-26T03:21:30Z",
                "created_at": "2026-11-26T03:20:41Z",
            }
        },
    )
