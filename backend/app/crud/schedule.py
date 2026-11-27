"""Truy vấn lịch tập (training.scheduled_workouts).

Mỗi lịch được đọc kèm buổi giáo án (+ tên giáo án) và buổi tập chưa xoá mềm gắn với lịch trong
cùng một truy vấn, nên một trang chỉ tốn một round-trip (không N+1).
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Select, and_, false, func, literal, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PlanStatus, SessionStatus
from app.models.training import ScheduledWorkout, WorkoutPlan, WorkoutPlanDay, WorkoutSession
from app.schemas.schedule import CreateScheduledWorkoutRequest, ScheduledWorkoutListQuery


def _schedule_rows_select() -> Select[Any]:
    """Cột phẳng của một lịch; uq_workout_sessions_scheduled_workout bảo đảm tối đa một buổi tập/lịch."""
    return (
        select(
            ScheduledWorkout.id,
            ScheduledWorkout.scheduled_date,
            ScheduledWorkout.title,
            ScheduledWorkout.notes,
            ScheduledWorkout.status,
            ScheduledWorkout.recovery_warning_ack_at,
            ScheduledWorkout.created_at,
            WorkoutPlanDay.id.label("plan_day_id"),
            WorkoutPlanDay.plan_id,
            WorkoutPlan.name.label("plan_name"),
            WorkoutPlanDay.day_no,
            WorkoutPlanDay.name.label("plan_day_name"),
            WorkoutSession.id.label("workout_session_id"),
            func.coalesce(WorkoutSession.status == SessionStatus.COMPLETED, false()).label("is_completed"),
        )
        .outerjoin(WorkoutPlanDay, WorkoutPlanDay.id == ScheduledWorkout.plan_day_id)
        .outerjoin(WorkoutPlan, WorkoutPlan.id == WorkoutPlanDay.plan_id)
        .outerjoin(
            WorkoutSession,
            and_(WorkoutSession.scheduled_workout_id == ScheduledWorkout.id, WorkoutSession.deleted_at.is_(None)),
        )
    )


async def list_schedule_rows(
    db: AsyncSession,
    user_id: uuid.UUID,
    query: ScheduledWorkoutListQuery,
    after: tuple[date, uuid.UUID] | None,
) -> list[Any]:
    """Một trang lịch của user, sắp `scheduled_date ASC, id ASC`; lọc ngày tính cả hai đầu.

    Lấy `limit + 1` dòng để tầng service biết còn trang sau mà không cần COUNT(*).
    """
    stmt = _schedule_rows_select().where(ScheduledWorkout.user_id == user_id)
    if query.from_date is not None:
        stmt = stmt.where(ScheduledWorkout.scheduled_date >= query.from_date)
    if query.to_date is not None:
        stmt = stmt.where(ScheduledWorkout.scheduled_date <= query.to_date)
    if query.status is not None:
        stmt = stmt.where(ScheduledWorkout.status == query.status)
    if after is not None:
        position = tuple_(literal(after[0]), literal(after[1]))
        stmt = stmt.where(tuple_(ScheduledWorkout.scheduled_date, ScheduledWorkout.id) > position)
    stmt = stmt.order_by(ScheduledWorkout.scheduled_date, ScheduledWorkout.id).limit(query.limit + 1)
    return list((await db.execute(stmt)).mappings().all())


async def get_schedule_row(db: AsyncSession, user_id: uuid.UUID, schedule_id: uuid.UUID) -> Any:
    """Một lịch của user với cùng bộ cột như danh sách; None nếu không có."""
    stmt = _schedule_rows_select().where(ScheduledWorkout.id == schedule_id, ScheduledWorkout.user_id == user_id)
    return (await db.execute(stmt)).mappings().one_or_none()


async def can_schedule_plan_day(db: AsyncSession, user_id: uuid.UUID, plan_day_id: uuid.UUID) -> bool:
    """Buổi thuộc giáo án của chính user (chưa xoá, chưa lưu trữ) hoặc giáo án mẫu đang dùng được."""
    own_plan = and_(WorkoutPlan.owner_user_id == user_id, WorkoutPlan.status != PlanStatus.ARCHIVED)
    template = and_(WorkoutPlan.owner_user_id.is_(None), WorkoutPlan.status == PlanStatus.ACTIVE)
    stmt = (
        select(WorkoutPlanDay.id)
        .join(WorkoutPlan, WorkoutPlan.id == WorkoutPlanDay.plan_id)
        .where(WorkoutPlanDay.id == plan_day_id, WorkoutPlan.deleted_at.is_(None), or_(own_plan, template))
    )
    return await db.scalar(stmt) is not None


async def create_schedule(
    db: AsyncSession,
    user_id: uuid.UUID,
    req: CreateScheduledWorkoutRequest,
    recovery_warning_ack_at: datetime | None,
) -> uuid.UUID:
    """Ghi lịch đã kiểm tra (status mặc định `planned` do DB sinh); không commit."""
    schedule = ScheduledWorkout(
        id=uuid.uuid4(),
        user_id=user_id,
        plan_day_id=req.plan_day_id,
        scheduled_date=req.scheduled_date,
        title=req.title,
        notes=req.notes,
        recovery_warning_ack_at=recovery_warning_ack_at,
    )
    db.add(schedule)
    await db.flush()
    return schedule.id
