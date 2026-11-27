"""Schema Pydantic cho /workout-plans và /scheduled-workouts (chức năng 2: Workout Routine).

Bộ field khớp bảng training.workout_plans, workout_plan_days, workout_plan_exercises (06_training.sql).
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic.json_schema import JsonDict

from app.models.enums import PlanStatus
from app.schemas.workout import ExerciseRefSchema

# Giới hạn kiểu cột DB (smallint/integer) để id quá lớn trả 422 thay vì lỗi tràn số từ DB.
_SMALLINT_MAX = 32767
_INTEGER_MAX = 2147483647

# Ví dụ lấy từ seed: giáo án "PPL của An" của demo, nhân bản từ mẫu T2 (Push / Pull / Legs).
_EXAMPLE_PLAN_EXERCISE: JsonDict = {
    "id": "6c1f0a52-4b7e-4d0a-9a51-2f6f5b8e7a10",
    "order_no": 1,
    "exercise": {"id": 26, "slug": "barbell-bench-press", "name": "Đẩy ngực với tạ đòn", "supports_ai_tracking": True},
    "target_sets": 4,
    "target_reps_min": 6,
    "target_reps_max": 8,
    "target_duration_seconds": None,
    "target_weight_kg": None,
    "target_rpe": 8.0,
    "rest_seconds": 150,
    "tempo_eccentric_s": 3,
    "tempo_pause_bottom_s": 1,
    "tempo_concentric_s": 1,
    "tempo_pause_top_s": 0,
    "notes": None,
}
_EXAMPLE_PLAN_DAY: JsonDict = {
    "id": "0b8d3c3e-1f4a-4c6e-8f0d-5a7b9c1d2e30",
    "day_no": 1,
    "name": "Push – Ngực/Vai/Tay sau",
    "notes": None,
    "exercises": [_EXAMPLE_PLAN_EXERCISE],
}
_EXAMPLE_PLAN: JsonDict = {
    "id": "dd1b5d27-91cb-46bf-be5a-cefb66fcaaf9",
    "name": "PPL của An",
    "description": "Chia nhóm cơ theo kiểu đẩy – kéo – chân, 3 hoặc 6 buổi/tuần, tập trung tăng cơ.",
    "source_plan_id": "5eed1000-0000-4000-8000-000000000002",
    "goal_type_id": 2,
    "difficulty_level_id": 2,
    "duration_weeks": 12,
    "status": "active",
    "days": [_EXAMPLE_PLAN_DAY],
    "created_at": "2026-10-14T04:05:56.505408Z",
    "updated_at": "2026-10-14T04:05:56.505408Z",
}


class WorkoutPlanListQuery(BaseModel):
    """Query của `GET /workout-plans`, gom vào một model (coding-standards §1)."""

    status: PlanStatus | None = Field(None, description="Lọc theo trạng thái giáo án")
    limit: int = Field(20, ge=1, le=100)
    cursor: str | None = Field(None, description="`next_cursor` của trang trước")


class WorkoutPlanExerciseResponse(BaseModel):
    """Một bài trong buổi giáo án: chỉ tiêu set/rep hoặc thời gian, tạ, RPE, nghỉ, tempo (giây)."""

    id: uuid.UUID
    order_no: int
    exercise: ExerciseRefSchema
    target_sets: int
    target_reps_min: int | None
    target_reps_max: int | None
    target_duration_seconds: int | None
    target_weight_kg: float | None
    target_rpe: float | None
    rest_seconds: int | None
    tempo_eccentric_s: int | None
    tempo_pause_bottom_s: int | None
    tempo_concentric_s: int | None
    tempo_pause_top_s: int | None
    notes: str | None

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"example": _EXAMPLE_PLAN_EXERCISE})


class WorkoutPlanDayResponse(BaseModel):
    """Một buổi trong chu kỳ giáo án, kèm các bài sắp theo `order_no`."""

    id: uuid.UUID
    day_no: int
    name: str
    notes: str | None
    exercises: list[WorkoutPlanExerciseResponse]

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"example": _EXAMPLE_PLAN_DAY})


class WorkoutPlanResponse(BaseModel):
    """Giáo án của user, kèm đầy đủ buổi (sắp theo `day_no`) và bài."""

    id: uuid.UUID
    name: str
    description: str | None
    source_plan_id: uuid.UUID | None = Field(..., description="Giáo án mẫu gốc nếu được nhân bản")
    goal_type_id: int | None
    difficulty_level_id: int | None
    duration_weeks: int | None
    status: PlanStatus
    days: list[WorkoutPlanDayResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"example": _EXAMPLE_PLAN})


# --- Tạo giáo án ---
_TEMPO_FIELDS = ("tempo_eccentric_s", "tempo_pause_bottom_s", "tempo_concentric_s", "tempo_pause_top_s")
TempoSeconds = Annotated[int | None, Field(None, ge=0, le=20)]
# Ví dụ tự soạn dùng id seed: 26 = barbell-bench-press; 1 = lose_fat; 1 = beginner.
_EXAMPLE_CREATE_PLAN: JsonDict = {
    "name": "Giáo án tự soạn",
    "description": "2 buổi/tuần",
    "goal_type_id": 1,
    "difficulty_level_id": 1,
    "duration_weeks": 6,
    "status": "active",
    "days": [
        {
            "name": "Thân trên",
            "notes": None,
            "exercises": [
                {
                    "exercise_id": 26, "target_sets": 4, "target_reps_min": 6, "target_reps_max": 8,
                    "target_weight_kg": 60, "target_rpe": 8, "rest_seconds": 150, "tempo_eccentric_s": 3,
                    "tempo_pause_bottom_s": 1, "tempo_concentric_s": 1, "tempo_pause_top_s": 0,
                }
            ],
        }
    ],
}


class WorkoutPlanExerciseSchema(BaseModel):
    """Một bài khi soạn giáo án; `order_no` do server gán theo vị trí trong mảng (từ 1).

    Ràng buộc khớp CHECK của training.workout_plan_exercises; ràng buộc chéo field báo ở
    `days.<i>.exercises.<j>`.
    """

    exercise_id: int = Field(..., ge=1, le=_INTEGER_MAX, description="Bài tập đã xuất bản (catalog.exercises.id)")
    target_sets: int = Field(..., ge=1, le=20)
    target_reps_min: int | None = Field(None, ge=1, le=100)
    target_reps_max: int | None = Field(None, ge=1, le=100)
    target_duration_seconds: int | None = Field(None, ge=1, le=7200, description="Giây mỗi hiệp (giữ tĩnh/cardio)")
    target_weight_kg: float | None = Field(None, ge=0, le=1000)
    target_rpe: float | None = Field(None, ge=1, le=10)
    rest_seconds: int | None = Field(None, ge=0, le=900)
    tempo_eccentric_s: TempoSeconds
    tempo_pause_bottom_s: TempoSeconds
    tempo_concentric_s: TempoSeconds
    tempo_pause_top_s: TempoSeconds
    notes: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def _check_targets(self) -> Self:
        if self.target_reps_min is None and self.target_duration_seconds is None:
            raise ValueError("Cần target_reps_min hoặc target_duration_seconds")
        reps_min, reps_max = self.target_reps_min, self.target_reps_max
        if reps_min is not None and reps_max is not None and reps_max < reps_min:
            raise ValueError("target_reps_max phải lớn hơn hoặc bằng target_reps_min")
        tempo_count = sum(getattr(self, name) is not None for name in _TEMPO_FIELDS)
        if tempo_count not in (0, len(_TEMPO_FIELDS)):
            raise ValueError("Tempo phải có đủ cả 4 pha hoặc bỏ trống cả 4")
        return self


class WorkoutPlanDaySchema(BaseModel):
    """Một buổi khi soạn giáo án; `day_no` do server gán theo vị trí trong mảng (từ 1)."""

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    notes: str | None = None
    exercises: list[WorkoutPlanExerciseSchema] = Field(..., min_length=1, max_length=30)


class CreateWorkoutPlanRequest(BaseModel):
    """Body `POST /workout-plans`: nhân bản mẫu (`source_plan_id`) hoặc tự soạn (`name` + `days`).

    Các field đều optional ở đây; việc bắt buộc theo từng cách tạo do service kiểm tra để lỗi
    luôn gắn đúng field (`name`, `days`, `source_plan_id`).
    """

    source_plan_id: uuid.UUID | None = Field(None, description="Giáo án mẫu cần nhân bản")
    name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=150)] | None = Field(
        None, description="Bắt buộc khi tự soạn; khi nhân bản mặc định bằng tên mẫu"
    )
    description: str | None = None
    goal_type_id: int | None = Field(None, ge=1, le=_SMALLINT_MAX)
    difficulty_level_id: int | None = Field(None, ge=1, le=_SMALLINT_MAX)
    duration_weeks: int | None = Field(None, ge=1, le=104)
    status: Literal[PlanStatus.DRAFT, PlanStatus.ACTIVE] = Field(PlanStatus.ACTIVE, description="draft | active")
    days: list[WorkoutPlanDaySchema] | None = Field(None, min_length=1, max_length=31, description="Chỉ khi tự soạn")

    # Ví dụ tự soạn; nhân bản chỉ cần {"source_plan_id": "5eed1000-0000-4000-8000-000000000002"} (mẫu T2).
    model_config = ConfigDict(json_schema_extra={"example": _EXAMPLE_CREATE_PLAN})
