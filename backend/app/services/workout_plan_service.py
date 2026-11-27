"""Nghiệp vụ /workout-plans (chức năng 2: lập kế hoạch tập luyện).

Mỗi giáo án được trả kèm đầy đủ buổi và bài; buổi và bài của cả trang được tải bằng
2 truy vấn gộp (không N+1).
"""

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DataValidationError, NotFoundError
from app.crud import body as body_crud
from app.crud import workout as workout_crud
from app.crud import workout_plan as crud
from app.models.training import WorkoutPlan, WorkoutPlanDay
from app.schemas.base import ErrorDetail, Page, build_page, decode_keyset_cursor
from app.schemas.workout import ExerciseRefSchema
from app.schemas.workout_routine import (
    CreateWorkoutPlanRequest,
    WorkoutPlanDayResponse,
    WorkoutPlanExerciseResponse,
    WorkoutPlanListQuery,
    WorkoutPlanResponse,
)

# Một message cho mọi lý do (không tồn tại, nháp, lưu trữ, của user khác) để không lộ giáo án có tồn tại.
_INVALID_TEMPLATE = "Giáo án mẫu không tồn tại hoặc không dùng được"

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


def _name_errors(req: CreateWorkoutPlanRequest, *, is_required: bool) -> list[ErrorDetail]:
    """`name` đã strip ở schema: rỗng luôn sai; thiếu chỉ sai khi tự soạn."""
    if req.name == "" or (is_required and req.name is None):
        return [ErrorDetail(field="name", message="Tên giáo án không được để trống", code="missing")]
    return []


async def _reference_errors(db: AsyncSession, req: CreateWorkoutPlanRequest) -> list[ErrorDetail]:
    """Mục tiêu và độ khó (nếu gửi) phải có trong danh mục."""
    checks = (
        ("goal_type_id", req.goal_type_id, "body.fitness_goal_types", "Mục tiêu không tồn tại"),
        ("difficulty_level_id", req.difficulty_level_id, "catalog.difficulty_levels", "Độ khó không tồn tại"),
    )
    errors = []
    for field, value, table, message in checks:
        if value is not None and not await body_crud.existing_ids(db, table, {value}):
            errors.append(ErrorDetail(field=field, message=message, code="invalid_reference"))
    return errors


async def _ensure_published_exercises(db: AsyncSession, req: CreateWorkoutPlanRequest) -> None:
    """Mọi bài phải published và chưa xoá; kiểm tra mỗi id một lần."""
    exercise_ids = {exercise.exercise_id for day in req.days or [] for exercise in day.exercises}
    for exercise_id in sorted(exercise_ids):
        if await workout_crud.get_published_exercise(db, exercise_id) is None:
            raise NotFoundError("exercise_not_found", "Không tìm thấy bài tập")


async def _create_from_template(
    db: AsyncSession, user_id: uuid.UUID, template_id: uuid.UUID, req: CreateWorkoutPlanRequest
) -> uuid.UUID:
    errors = _name_errors(req, is_required=False)
    if req.days is not None:
        errors.append(ErrorDetail(field="days", message="Không gửi days khi nhân bản giáo án mẫu", code="value_error"))
    if await crud.get_usable_template(db, template_id) is None:
        errors.append(ErrorDetail(field="source_plan_id", message=_INVALID_TEMPLATE, code="invalid_reference"))
    if errors:
        raise DataValidationError(errors)
    return await crud.clone_template(db, user_id, req)


async def _create_custom(db: AsyncSession, user_id: uuid.UUID, req: CreateWorkoutPlanRequest) -> uuid.UUID:
    errors = _name_errors(req, is_required=True)
    if req.days is None:
        errors.append(ErrorDetail(field="days", message="Giáo án tự soạn cần ít nhất một buổi", code="missing"))
    errors += await _reference_errors(db, req)
    if errors:
        raise DataValidationError(errors)
    await _ensure_published_exercises(db, req)
    return await crud.create_custom_plan(db, user_id, req)


async def create_plan(db: AsyncSession, user_id: uuid.UUID, req: CreateWorkoutPlanRequest) -> WorkoutPlanResponse:
    """Tạo giáo án cho chính user: nhân bản mẫu (`source_plan_id`) hoặc tự soạn (`name` + `days`).

    Mọi kiểm tra chạy trước khi ghi; commit đúng một lần.
    """
    if req.source_plan_id is not None:
        plan_id = await _create_from_template(db, user_id, req.source_plan_id, req)
    else:
        plan_id = await _create_custom(db, user_id, req)
    await db.commit()
    plan = await crud.reload_plan(db, plan_id)
    days_by_plan = await _days_by_plan(db, [plan.id])
    return _plan_response(plan, days_by_plan.get(plan.id, []))
