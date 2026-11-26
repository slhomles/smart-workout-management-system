"""Nghiệp vụ /workout-plans (chức năng 2: lập kế hoạch tập luyện).

Mỗi giáo án được trả kèm đầy đủ buổi và bài; buổi và bài của cả trang được tải bằng
2 truy vấn gộp (không N+1).
"""

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import workout_plan as crud
from app.models.training import WorkoutPlan, WorkoutPlanDay
from app.schemas.base import Page, build_page, decode_keyset_cursor
from app.schemas.workout import ExerciseRefSchema
from app.schemas.workout_routine import (
    WorkoutPlanDayResponse,
    WorkoutPlanExerciseResponse,
    WorkoutPlanListQuery,
    WorkoutPlanResponse,
)

_PLAN_EXERCISE_FIELDS = (
    "id", "order_no", "target_sets", "target_reps_min", "target_reps_max", "target_duration_seconds",
    "target_weight_kg", "target_rpe", "rest_seconds", "tempo_eccentric_s", "tempo_pause_bottom_s",
    "tempo_concentric_s", "tempo_pause_top_s", "notes",
)


def _plan_exercise_response(row: Any) -> WorkoutPlanExerciseResponse:
    exercise = ExerciseRefSchema(
        id=row["exercise_id"], slug=row["slug"], name=row["name"], supports_ai_tracking=row["supports_ai_tracking"]
    )
    return WorkoutPlanExerciseResponse(exercise=exercise, **{name: row[name] for name in _PLAN_EXERCISE_FIELDS})


def _plan_day_response(day: WorkoutPlanDay, exercises: list[WorkoutPlanExerciseResponse]) -> WorkoutPlanDayResponse:
    return WorkoutPlanDayResponse(id=day.id, day_no=day.day_no, name=day.name, notes=day.notes, exercises=exercises)


def _plan_response(plan: WorkoutPlan, days: list[WorkoutPlanDayResponse]) -> WorkoutPlanResponse:
    return WorkoutPlanResponse(
        id=plan.id,
        name=plan.name,
        description=plan.description,
        source_plan_id=plan.source_plan_id,
        goal_type_id=plan.goal_type_id,
        difficulty_level_id=plan.difficulty_level_id,
        duration_weeks=plan.duration_weeks,
        status=plan.status,
        days=days,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


async def _days_by_plan(
    db: AsyncSession, plan_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[WorkoutPlanDayResponse]]:
    """Ráp buổi và bài cho nhiều giáo án; crud đã sắp sẵn theo `day_no`/`order_no`."""
    days = await crud.list_plan_days(db, plan_ids)
    exercises_by_day: dict[uuid.UUID, list[WorkoutPlanExerciseResponse]] = defaultdict(list)
    for row in await crud.list_plan_exercise_rows(db, [day.id for day in days]):
        exercises_by_day[row["plan_day_id"]].append(_plan_exercise_response(row))
    days_by_plan: dict[uuid.UUID, list[WorkoutPlanDayResponse]] = defaultdict(list)
    for day in days:
        days_by_plan[day.plan_id].append(_plan_day_response(day, exercises_by_day[day.id]))
    return days_by_plan


async def list_plans(
    db: AsyncSession, user_id: uuid.UUID, query: WorkoutPlanListQuery
) -> Page[WorkoutPlanResponse]:
    """Trang giáo án của chính user (không gồm giáo án mẫu, đã xoá mềm), mới tạo trước."""
    plans = await crud.list_plans(db, user_id, query, decode_keyset_cursor(query.cursor, "created_at"))
    days_by_plan = await _days_by_plan(db, [plan.id for plan in plans[: query.limit]])
    return build_page(
        plans,
        query.limit,
        to_item=lambda plan: _plan_response(plan, days_by_plan.get(plan.id, [])),
        cursor_of=lambda plan: {"created_at": plan.created_at.isoformat(), "id": str(plan.id)},
    )
