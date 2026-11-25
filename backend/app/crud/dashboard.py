"""Truy vấn tổng hợp cho Dashboard & báo cáo — chỉ đọc từ view có sẵn (doc 05 §2.2, §6.1)."""

import uuid
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def latest_metrics(db: AsyncSession, user_id: uuid.UUID) -> Any | None:
    sql = """
    SELECT measurement_id, measured_at, weight_kg, body_fat_pct, bmi, bmi_category, bmr_kcal, tdee_kcal
    FROM body.v_latest_body_metrics WHERE user_id = :user_id
    """
    return (await db.execute(text(sql), {"user_id": user_id})).mappings().first()


async def session_totals(db: AsyncSession, user_id: uuid.UUID, tz: str, start: date, end: date) -> Any:
    """Tổng các buổi `completed` có ngày bắt đầu (theo múi giờ user) trong [start, end)."""
    sql = """
    SELECT count(*)                               AS sessions_completed,
           coalesce(sum(est_calories_kcal), 0)    AS est_calories_kcal,
           coalesce(sum(total_volume_kg), 0)      AS total_volume_kg,
           coalesce(sum(duration_minutes), 0)     AS duration_minutes,
           coalesce(sum(completed_set_count), 0)  AS completed_set_count,
           coalesce(sum(total_reps), 0)           AS total_reps
    FROM training.v_session_summary
    WHERE user_id = :user_id AND status = 'completed'
      AND (started_at AT TIME ZONE :tz)::date >= :start
      AND (started_at AT TIME ZONE :tz)::date <  :end
    """
    return (await db.execute(text(sql), {"user_id": user_id, "tz": tz, "start": start, "end": end})).mappings().one()


async def has_session_in_progress(db: AsyncSession, user_id: uuid.UUID) -> bool:
    sql = "SELECT EXISTS (SELECT 1 FROM training.v_session_summary WHERE user_id = :user_id AND status = 'in_progress')"
    return bool(await db.scalar(text(sql), {"user_id": user_id}))


async def adherence(db: AsyncSession, user_id: uuid.UUID, start: date, end: date) -> Any:
    """Gộp v_weekly_adherence của các tuần bắt đầu trong [start, end)."""
    sql = """
    SELECT coalesce(sum(planned_count), 0)    AS planned_count,
           coalesce(sum(completed_count), 0)  AS completed_count,
           coalesce(sum(skipped_count), 0)    AS skipped_count,
           round(100.0 * sum(completed_count) / nullif(sum(planned_count), 0), 1) AS adherence_pct
    FROM training.v_weekly_adherence
    WHERE user_id = :user_id AND week_start >= :start AND week_start < :end
    """
    return (await db.execute(text(sql), {"user_id": user_id, "start": start, "end": end})).mappings().one()


async def latest_plateau_flag(db: AsyncSession, user_id: uuid.UUID) -> bool:
    sql = """
    SELECT is_plateau FROM body.v_weekly_weight_trend
    WHERE user_id = :user_id ORDER BY week_start DESC LIMIT 1
    """
    return bool(await db.scalar(text(sql), {"user_id": user_id}))


async def weekly_weight_trend(db: AsyncSession, user_id: uuid.UUID, start: date) -> list[Any]:
    sql = """
    SELECT week_start, avg_weight_kg, min_weight_kg, max_weight_kg, avg_body_fat_pct,
           measurement_count, change_kg, is_plateau
    FROM body.v_weekly_weight_trend
    WHERE user_id = :user_id AND week_start >= :start
    ORDER BY week_start
    """
    return list((await db.execute(text(sql), {"user_id": user_id, "start": start})).mappings().all())


async def weekly_training(db: AsyncSession, user_id: uuid.UUID, tz: str, start: date) -> list[Any]:
    sql = """
    SELECT date_trunc('week', started_at AT TIME ZONE :tz)::date AS week_start,
           count(*)                            AS sessions_completed,
           coalesce(sum(est_calories_kcal), 0) AS est_calories_kcal
    FROM training.v_session_summary
    WHERE user_id = :user_id AND status = 'completed'
      AND (started_at AT TIME ZONE :tz)::date >= :start
    GROUP BY 1
    """
    return list((await db.execute(text(sql), {"user_id": user_id, "tz": tz, "start": start})).mappings().all())


async def weight_in_period(db: AsyncSession, user_id: uuid.UUID, tz: str, start: date, end: date) -> Any:
    sql = """
    SELECT round(avg(weight_kg), 2)                              AS avg_weight_kg,
           (array_agg(weight_kg ORDER BY measured_at DESC))[1]
             - (array_agg(weight_kg ORDER BY measured_at))[1]    AS weight_change_kg
    FROM body.body_measurements
    WHERE user_id = :user_id
      AND (measured_at AT TIME ZONE :tz)::date >= :start
      AND (measured_at AT TIME ZONE :tz)::date <  :end
    """
    return (await db.execute(text(sql), {"user_id": user_id, "tz": tz, "start": start, "end": end})).mappings().one()
