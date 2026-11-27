"""Truy vấn giáo án (training.workout_plans, workout_plan_days, workout_plan_exercises).

Bài tập đọc kèm từ catalog.exercises (module Catalog, chỉ đọc qua `text()`).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import literal, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base
from app.models.enums import PlanStatus
from app.models.training import WorkoutPlan, WorkoutPlanDay, WorkoutPlanExercise
from app.schemas.workout_routine import CreateWorkoutPlanRequest, WorkoutPlanDaySchema, WorkoutPlanListQuery


async def list_plans(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    query: WorkoutPlanListQuery,
    after: tuple[datetime, uuid.UUID] | None,
) -> list[WorkoutPlan]:
    """Một trang giáo án của user (bỏ giáo án mẫu và đã xoá mềm), sắp `created_at DESC, id DESC`.

    Lấy `limit + 1` dòng để tầng service biết còn trang sau mà không cần COUNT(*).
    """
    stmt = select(WorkoutPlan).where(WorkoutPlan.owner_user_id == owner_user_id, WorkoutPlan.deleted_at.is_(None))
    if query.status is not None:
        stmt = stmt.where(WorkoutPlan.status == query.status)
    if after is not None:
        stmt = stmt.where(tuple_(WorkoutPlan.created_at, WorkoutPlan.id) < tuple_(literal(after[0]), literal(after[1])))
    stmt = stmt.order_by(WorkoutPlan.created_at.desc(), WorkoutPlan.id.desc()).limit(query.limit + 1)
    return list((await db.scalars(stmt)).all())


async def list_plan_days(db: AsyncSession, plan_ids: list[uuid.UUID]) -> list[WorkoutPlanDay]:
    """Các buổi của nhiều giáo án trong một truy vấn, sắp theo giáo án rồi `day_no`."""
    if not plan_ids:
        return []
    stmt = (
        select(WorkoutPlanDay)
        .where(WorkoutPlanDay.plan_id.in_(plan_ids))
        .order_by(WorkoutPlanDay.plan_id, WorkoutPlanDay.day_no)
    )
    return list((await db.scalars(stmt)).all())


_PLAN_EXERCISE_SELECT = """
SELECT pe.id, pe.plan_day_id, pe.order_no, pe.target_sets, pe.target_reps_min, pe.target_reps_max,
       pe.target_duration_seconds, pe.target_weight_kg, pe.target_rpe, pe.rest_seconds,
       pe.tempo_eccentric_s, pe.tempo_pause_bottom_s, pe.tempo_concentric_s, pe.tempo_pause_top_s, pe.notes,
       e.id AS exercise_id, e.slug, e.name, e.supports_ai_tracking
FROM training.workout_plan_exercises pe
JOIN catalog.exercises e ON e.id = pe.exercise_id
WHERE pe.plan_day_id = ANY(:ids)
ORDER BY pe.plan_day_id, pe.order_no
"""


async def list_plan_exercise_rows(db: AsyncSession, plan_day_ids: list[uuid.UUID]) -> list[Any]:
    """Các bài của nhiều buổi trong một truy vấn, kèm thông tin tóm tắt bài tập, sắp theo `order_no`."""
    if not plan_day_ids:
        return []
    return list((await db.execute(text(_PLAN_EXERCISE_SELECT), {"ids": plan_day_ids})).mappings().all())


async def reload_plan(db: AsyncSession, plan_id: uuid.UUID) -> WorkoutPlan:
    """Đọc lại giáo án vừa ghi (kể cả `created_at`/`updated_at` do DB sinh), ghi đè bản trong session."""
    return await db.get_one(WorkoutPlan, plan_id, populate_existing=True)


async def get_usable_template(db: AsyncSession, plan_id: uuid.UUID) -> WorkoutPlan | None:
    """Giáo án mẫu dùng được: của hệ thống, `active`, chưa xoá mềm (index ix_workout_plans_templates)."""
    stmt = select(WorkoutPlan).where(
        WorkoutPlan.id == plan_id,
        WorkoutPlan.owner_user_id.is_(None),
        WorkoutPlan.status == PlanStatus.ACTIVE,
        WorkoutPlan.deleted_at.is_(None),
    )
    return await db.scalar(stmt)


# Cùng cách nhân bản với test_seed.clone_plan (seeds/90_test_users.sql); created_at/updated_at để DB sinh.
_CLONE_PLAN = """
INSERT INTO training.workout_plans (owner_user_id, source_plan_id, name, description, goal_type_id,
                                    difficulty_level_id, duration_weeks, status)
SELECT :owner_user_id, t.id, coalesce(:name, t.name), t.description, t.goal_type_id, t.difficulty_level_id,
       t.duration_weeks, CAST(:status AS training.plan_status)
FROM training.workout_plans t WHERE t.id = :template_id
RETURNING id
"""
_CLONE_DAYS = """
INSERT INTO training.workout_plan_days (plan_id, day_no, name, notes)
SELECT :plan_id, d.day_no, d.name, d.notes
FROM training.workout_plan_days d WHERE d.plan_id = :template_id
"""
_CLONE_EXERCISES = """
INSERT INTO training.workout_plan_exercises (plan_day_id, exercise_id, order_no, target_sets, target_reps_min,
       target_reps_max, target_duration_seconds, target_weight_kg, target_rpe, rest_seconds,
       tempo_eccentric_s, tempo_pause_bottom_s, tempo_concentric_s, tempo_pause_top_s, notes)
SELECT nd.id, pe.exercise_id, pe.order_no, pe.target_sets, pe.target_reps_min,
       pe.target_reps_max, pe.target_duration_seconds, pe.target_weight_kg, pe.target_rpe, pe.rest_seconds,
       pe.tempo_eccentric_s, pe.tempo_pause_bottom_s, pe.tempo_concentric_s, pe.tempo_pause_top_s, pe.notes
FROM training.workout_plan_exercises pe
JOIN training.workout_plan_days od ON od.id = pe.plan_day_id AND od.plan_id = :template_id
JOIN training.workout_plan_days nd ON nd.plan_id = :plan_id AND nd.day_no = od.day_no
"""


async def clone_template(
    db: AsyncSession, owner_user_id: uuid.UUID, req: CreateWorkoutPlanRequest
) -> uuid.UUID:
    """Nhân bản giáo án mẫu `req.source_plan_id` (đã kiểm tra) kèm toàn bộ buổi/bài; không commit.

    `name` không gửi thì lấy tên mẫu.
    """
    template_id = req.source_plan_id
    params = {"owner_user_id": owner_user_id, "name": req.name, "status": req.status.value, "template_id": template_id}
    plan_id: uuid.UUID = await db.scalar(text(_CLONE_PLAN), params)
    copy_params = {"plan_id": plan_id, "template_id": template_id}
    await db.execute(text(_CLONE_DAYS), copy_params)
    await db.execute(text(_CLONE_EXERCISES), copy_params)
    return plan_id


def _day_rows(plan_id: uuid.UUID, day_no: int, day: WorkoutPlanDaySchema) -> list[Base]:
    """Dòng buổi + các dòng bài; `order_no` theo vị trí trong mảng, bắt đầu từ 1."""
    day_row = WorkoutPlanDay(id=uuid.uuid4(), plan_id=plan_id, day_no=day_no, name=day.name, notes=day.notes)
    exercise_rows: list[Base] = [
        WorkoutPlanExercise(plan_day_id=day_row.id, order_no=order_no, **exercise.model_dump())
        for order_no, exercise in enumerate(day.exercises, start=1)
    ]
    return [day_row, *exercise_rows]


async def create_custom_plan(
    db: AsyncSession, owner_user_id: uuid.UUID, req: CreateWorkoutPlanRequest
) -> uuid.UUID:
    """Ghi giáo án tự soạn (đã kiểm tra) cùng buổi/bài trong một lần flush; không commit.

    Id buổi sinh ở ứng dụng để gắn bài vào buổi mà không cần flush từng buổi.
    """
    plan = WorkoutPlan(
        id=uuid.uuid4(),
        owner_user_id=owner_user_id,
        name=req.name,
        description=req.description,
        goal_type_id=req.goal_type_id,
        difficulty_level_id=req.difficulty_level_id,
        duration_weeks=req.duration_weeks,
        status=req.status,
    )
    rows: list[Base] = [plan]
    for day_no, day in enumerate(req.days or [], start=1):
        rows.extend(_day_rows(plan.id, day_no, day))
    db.add_all(rows)
    await db.flush()
    return plan.id
