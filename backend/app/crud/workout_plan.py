"""Truy vấn giáo án (training.workout_plans, workout_plan_days, workout_plan_exercises).

Bài tập đọc kèm từ catalog.exercises (module Catalog, chỉ đọc qua `text()`).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import literal, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training import WorkoutPlan, WorkoutPlanDay
from app.schemas.workout_routine import WorkoutPlanListQuery


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
