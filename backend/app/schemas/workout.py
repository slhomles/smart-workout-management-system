"""Schema Pydantic cho /workout-sessions — ghi buổi tập, hiệp, rep và tempo (chức năng 6).
Giới hạn giá trị khớp CHECK trong 06_training.sql."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.models.enums import AddedVia, LogSource, SessionStatus, SetType


# --- Buổi tập ---
class CreateWorkoutSessionRequest(BaseModel):
    name: str | None = Field(None, max_length=150)
    notes: str | None = Field(None, max_length=2000)

    model_config = ConfigDict(json_schema_extra={"example": {"name": "Đẩy ngực tối thứ Ba"}})


class FinishWorkoutSessionRequest(BaseModel):
    status: Literal[SessionStatus.COMPLETED, SessionStatus.ABANDONED] = SessionStatus.COMPLETED
    session_rpe: float | None = Field(None, ge=1, le=10)
    notes: str | None = Field(None, max_length=2000)


class WorkoutSessionSummaryResponse(BaseModel):
    """Một dòng của training.v_session_summary."""

    id: uuid.UUID
    name: str | None
    status: SessionStatus
    started_at: datetime
    ended_at: datetime | None
    duration_minutes: float | None
    exercise_count: int
    completed_set_count: int
    total_reps: int
    total_volume_kg: float
    est_calories_kcal: int | None


# --- Rep & tempo ---
class RepEventInput(BaseModel):
    """Một rep do máy trạng thái (FSM) trên thiết bị ghi nhận."""

    rep_no: int = Field(..., gt=0)
    start_offset_ms: int = Field(..., ge=0)
    eccentric_ms: int = Field(..., ge=0, description="Pha hạ")
    pause_bottom_ms: int = Field(0, ge=0)
    concentric_ms: int = Field(..., ge=0, description="Pha đẩy lên")
    pause_top_ms: int = Field(0, ge=0)
    min_joint_angle_deg: float | None = Field(None, ge=0, le=180)
    max_joint_angle_deg: float | None = Field(None, ge=0, le=180)
    is_full_rom: bool = True

    @model_validator(mode="after")
    def _angles(self) -> "RepEventInput":
        if (
            self.min_joint_angle_deg is not None
            and self.max_joint_angle_deg is not None
            and self.max_joint_angle_deg < self.min_joint_angle_deg
        ):
            raise ValueError("max_joint_angle_deg phải ≥ min_joint_angle_deg")
        return self


class RepEventResponse(RepEventInput):
    pass


class SetTempoSchema(BaseModel):
    """Tempo trung bình mỗi pha & thời gian chịu tải, từ training.v_set_tempo."""

    rep_count: int
    avg_eccentric_ms: int
    avg_pause_bottom_ms: int
    avg_concentric_ms: int
    avg_pause_top_ms: int
    time_under_tension_ms: int
    full_rom_pct: float


# --- Hiệp ---
class CreateExerciseSetRequest(BaseModel):
    set_type: SetType = SetType.WORKING
    reps: int | None = Field(None, ge=0, le=1000, description="Bỏ trống khi gửi rep_events: server lấy = số rep")
    weight_kg: float | None = Field(None, ge=0, le=1000)
    duration_seconds: int | None = Field(None, ge=0, le=86400)
    distance_m: float | None = Field(None, ge=0)
    rpe: float | None = Field(None, ge=1, le=10, multiple_of=0.5)
    rest_seconds: int | None = Field(None, ge=0, le=3600)
    source: LogSource = LogSource.MANUAL
    completed_at: AwareDatetime | None = Field(None, description="Mặc định là thời điểm hiện tại")
    rep_events: list[RepEventInput] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def _validate(self) -> "CreateExerciseSetRequest":
        if self.rep_events:
            if self.source == LogSource.MANUAL:
                raise ValueError("rep_events chỉ dùng với source ai_realtime/ai_video")
            numbers = sorted(r.rep_no for r in self.rep_events)
            if numbers != list(range(1, len(numbers) + 1)):
                raise ValueError("rep_no phải liên tục từ 1 và không trùng")
        if self.reps is None and not self.rep_events and self.duration_seconds is None and self.distance_m is None:
            raise ValueError("Cần ít nhất một trong reps, duration_seconds, distance_m hoặc rep_events")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "set_type": "working",
                "weight_kg": 60,
                "source": "ai_realtime",
                "rep_events": [
                    {"rep_no": 1, "start_offset_ms": 0, "eccentric_ms": 3000, "pause_bottom_ms": 200,
                     "concentric_ms": 1000, "pause_top_ms": 300, "min_joint_angle_deg": 78.5,
                     "max_joint_angle_deg": 172.0, "is_full_rom": True},
                    {"rep_no": 2, "start_offset_ms": 4600, "eccentric_ms": 2900, "pause_bottom_ms": 150,
                     "concentric_ms": 1100, "pause_top_ms": 250, "min_joint_angle_deg": 80.0,
                     "max_joint_angle_deg": 171.0, "is_full_rom": True},
                ],
            }
        }
    )


class UpdateExerciseSetRequest(BaseModel):
    """PATCH: user sửa lại số AI đếm (reps), mức tạ, RPE..."""

    set_type: SetType | None = None
    reps: int | None = Field(None, ge=0, le=1000)
    weight_kg: float | None = Field(None, ge=0, le=1000)
    duration_seconds: int | None = Field(None, ge=0, le=86400)
    distance_m: float | None = Field(None, ge=0)
    rpe: float | None = Field(None, ge=1, le=10, multiple_of=0.5)
    rest_seconds: int | None = Field(None, ge=0, le=3600)


class ExerciseSetResponse(BaseModel):
    id: int
    set_no: int
    set_type: SetType
    reps: int | None
    weight_kg: float | None
    duration_seconds: int | None
    distance_m: float | None
    rpe: float | None
    rest_seconds: int | None
    source: LogSource
    completed_at: datetime | None
    volume_kg: float | None = Field(..., description="reps × weight_kg (training.v_set_metrics)")
    est_1rm_kg: float | None = Field(..., description="1RM ước tính Epley (training.v_set_metrics)")
    tempo: SetTempoSchema | None = Field(..., description="NULL khi hiệp không có dữ liệu rep từ AI")


class ExerciseSetDetailResponse(ExerciseSetResponse):
    rep_events: list[RepEventResponse]


# --- Bài trong buổi ---
class AddSessionExerciseRequest(BaseModel):
    exercise_id: int = Field(..., ge=1)
    added_via: Literal[AddedVia.MANUAL, AddedVia.WIKI, AddedVia.EQUIPMENT_SCAN] = AddedVia.MANUAL
    notes: str | None = Field(None, max_length=500)

    model_config = ConfigDict(json_schema_extra={"example": {"exercise_id": 10, "added_via": "wiki"}})


class ExerciseRefSchema(BaseModel):
    id: int
    slug: str
    name: str
    supports_ai_tracking: bool


class SessionExerciseResponse(BaseModel):
    id: uuid.UUID
    exercise: ExerciseRefSchema
    order_no: int
    added_via: AddedVia
    notes: str | None
    sets: list[ExerciseSetResponse]


class WorkoutSessionResponse(WorkoutSessionSummaryResponse):
    session_rpe: float | None
    notes: str | None
    exercises: list[SessionExerciseResponse]
