"""
Nghiệp vụ /dashboard (chức năng 3): tổng quan trong ngày và xu hướng cân nặng.
TODO(dashboard): cache "hôm nay" trên Redis (design-overview §8) khi hạ tầng Redis sẵn sàng.
"""

import uuid
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import body as body_crud
from app.crud import dashboard as crud
from app.schemas.dashboard import (
    DashboardResponse,
    LatestMetricsSchema,
    TodaySummarySchema,
    TrendRange,
    WeekProgressSchema,
    WeightTrendPointSchema,
    WeightTrendResponse,
)
from app.services import body_service

RANGE_WEEKS: dict[str, int] = {"week": 1, "month": 5, "3months": 13}


async def get_dashboard(db: AsyncSession, user_id: uuid.UUID) -> DashboardResponse:
    tz = await body_crud.get_user_timezone(db, user_id)
    today = await body_crud.local_today(db, tz)
    week_start = today - timedelta(days=today.weekday())

    latest = await crud.latest_metrics(db, user_id)
    goal = await body_crud.get_active_goal(db, user_id)
    day = await crud.session_totals(db, user_id, tz, today, today + timedelta(days=1))
    week_sessions = await crud.session_totals(db, user_id, tz, week_start, week_start + timedelta(days=7))
    week_plan = await crud.adherence(db, user_id, week_start, week_start + timedelta(days=7))

    return DashboardResponse(
        date=today,
        timezone=tz,
        latest_metrics=LatestMetricsSchema(**latest) if latest else None,
        active_goal=await body_service.goal_response(db, goal) if goal else None,
        today=TodaySummarySchema(
            sessions_completed=day["sessions_completed"],
            est_calories_burned_kcal=day["est_calories_kcal"],
            total_volume_kg=day["total_volume_kg"],
            duration_minutes=day["duration_minutes"],
            has_session_in_progress=await crud.has_session_in_progress(db, user_id),
        ),
        this_week=WeekProgressSchema(
            week_start=week_start,
            planned_count=week_plan["planned_count"],
            completed_planned_count=week_plan["completed_count"],
            skipped_count=week_plan["skipped_count"],
            adherence_pct=week_plan["adherence_pct"],
            sessions_completed=week_sessions["sessions_completed"],
        ),
        is_plateau=await crud.latest_plateau_flag(db, user_id),
    )


async def get_weight_trend(db: AsyncSession, user_id: uuid.UUID, range_: TrendRange) -> WeightTrendResponse:
    tz = await body_crud.get_user_timezone(db, user_id)
    today = await body_crud.local_today(db, tz)
    current_week = today - timedelta(days=today.weekday())
    start = current_week - timedelta(weeks=RANGE_WEEKS[range_] - 1)

    weights = {r["week_start"]: r for r in await crud.weekly_weight_trend(db, user_id, start)}
    training = {r["week_start"]: r for r in await crud.weekly_training(db, user_id, tz, start)}

    points = []
    for week in sorted(set(weights) | set(training)):
        w = weights.get(week)
        t = training.get(week)
        points.append(
            WeightTrendPointSchema(
                week_start=week,
                avg_weight_kg=w["avg_weight_kg"] if w else None,
                min_weight_kg=w["min_weight_kg"] if w else None,
                max_weight_kg=w["max_weight_kg"] if w else None,
                avg_body_fat_pct=w["avg_body_fat_pct"] if w else None,
                measurement_count=w["measurement_count"] if w else 0,
                change_kg=w["change_kg"] if w else None,
                is_plateau=w["is_plateau"] if w else False,
                sessions_completed=t["sessions_completed"] if t else 0,
                est_calories_burned_kcal=t["est_calories_kcal"] if t else 0,
            )
        )
    return WeightTrendResponse(
        range=range_,
        from_date=start,
        to_date=today,
        points=points,
        is_plateau=await crud.latest_plateau_flag(db, user_id),
    )
