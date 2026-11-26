"""Schema Pydantic cho /workout-plans và /scheduled-workouts (chức năng 2: Workout Routine).

Bộ field khớp bảng training.workout_plans, workout_plan_days, workout_plan_exercises (06_training.sql).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import JsonDict

from app.models.enums import PlanStatus
from app.schemas.workout import ExerciseRefSchema

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
