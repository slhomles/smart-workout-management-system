"""Truy vấn schema `body` (không chứa nghiệp vụ). Chỉ số dẫn xuất đọc từ view body.v_body_metrics."""

import uuid
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, literal, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import UserProfile
from app.models.body import (
    ActivityLevel,
    BodyCircumference,
    BodySite,
    FitnessGoalType,
    UserBodyProfile,
    UserGoal,
)
from app.models.enums import GoalStatus

DEFAULT_TIMEZONE = "Asia/Ho_Chi_Minh"


# --- Danh mục ---
async def list_activity_levels(db: AsyncSession) -> Sequence[ActivityLevel]:
    return (await db.scalars(select(ActivityLevel).order_by(ActivityLevel.display_order))).all()


async def list_goal_types(db: AsyncSession) -> Sequence[FitnessGoalType]:
    return (await db.scalars(select(FitnessGoalType).order_by(FitnessGoalType.display_order))).all()


async def list_body_sites(db: AsyncSession) -> Sequence[BodySite]:
    return (await db.scalars(select(BodySite).order_by(BodySite.display_order))).all()


async def existing_ids(db: AsyncSession, table: str, ids: set[int]) -> set[int]:
    """Lọc các id tồn tại trong bảng danh mục (tên bảng do code truyền, không từ client)."""
    if not ids:
        return set()
    rows = await db.execute(text(f"SELECT id FROM {table} WHERE id = ANY(:ids)"), {"ids": list(ids)})
    return {r[0] for r in rows}


# --- Thời gian theo user ---
async def get_user_timezone(db: AsyncSession, user_id: uuid.UUID) -> str:
    tz = await db.scalar(select(UserProfile.timezone).where(UserProfile.user_id == user_id))
    return tz or DEFAULT_TIMEZONE


async def local_today(db: AsyncSession, tz: str) -> date:
    return await db.scalar(text("SELECT (now() AT TIME ZONE :tz)::date"), {"tz": tz})


async def db_now(db: AsyncSession) -> datetime:
    return await db.scalar(text("SELECT now()"))


# --- Hồ sơ thể chất ---
async def get_body_profile(db: AsyncSession, user_id: uuid.UUID) -> UserBodyProfile | None:
    return await db.get(UserBodyProfile, user_id)


# --- Lần đo ---
_MEASUREMENT_SELECT = """
SELECT m.id, m.measured_at, m.weight_kg, m.body_fat_pct, m.muscle_mass_kg, m.source, m.note,
       m.created_at, m.updated_at,
       v.age_years, v.bmi, v.bmi_category, v.lean_body_mass_kg, v.bmr_kcal,
       v.bmr_katch_mcardle_kcal, v.tdee_kcal, v.activity_level_code
FROM body.body_measurements m
JOIN body.v_body_metrics v ON v.measurement_id = m.id
WHERE m.user_id = :user_id
"""


async def get_measurement_row(db: AsyncSession, user_id: uuid.UUID, measurement_id: uuid.UUID) -> Any | None:
    sql = _MEASUREMENT_SELECT + " AND m.id = :id"
    return (await db.execute(text(sql), {"user_id": user_id, "id": measurement_id})).mappings().first()


async def list_measurement_rows(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    from_: datetime | None,
    to: datetime | None,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[Any]:
    sql = _MEASUREMENT_SELECT
    params: dict[str, Any] = {"user_id": user_id, "limit": limit}
    if from_ is not None:
        sql += " AND m.measured_at >= :from_"
        params["from_"] = from_
    if to is not None:
        sql += " AND m.measured_at < :to"
        params["to"] = to
    if after is not None:
        sql += " AND (m.measured_at, m.id) < (:c_at, :c_id)"
        params["c_at"], params["c_id"] = after
    sql += " ORDER BY m.measured_at DESC, m.id DESC LIMIT :limit"
    return list((await db.execute(text(sql), params)).mappings().all())


async def measurement_exists_at(
    db: AsyncSession, user_id: uuid.UUID, measured_at: datetime, exclude_id: uuid.UUID | None = None
) -> bool:
    sql = "SELECT 1 FROM body.body_measurements WHERE user_id = :user_id AND measured_at = :at"
    params: dict[str, Any] = {"user_id": user_id, "at": measured_at}
    if exclude_id is not None:
        sql += " AND id <> :exclude_id"
        params["exclude_id"] = exclude_id
    return (await db.scalar(text(sql), params)) is not None


async def circumferences_for(db: AsyncSession, measurement_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[Any]]:
    result: dict[uuid.UUID, list[Any]] = {mid: [] for mid in measurement_ids}
    if not measurement_ids:
        return result
    rows = await db.execute(
        select(
            BodyCircumference.measurement_id,
            BodyCircumference.body_site_id,
            BodySite.code.label("body_site_code"),
            BodySite.name.label("body_site_name"),
            BodyCircumference.value_cm,
        )
        .join(BodySite, BodySite.id == BodyCircumference.body_site_id)
        .where(BodyCircumference.measurement_id.in_(measurement_ids))
        .order_by(BodySite.display_order)
    )
    for row in rows.mappings():
        result[row["measurement_id"]].append(row)
    return result


async def replace_circumferences(
    db: AsyncSession, measurement_id: uuid.UUID, items: list[tuple[int, float]]
) -> None:
    await db.execute(delete(BodyCircumference).where(BodyCircumference.measurement_id == measurement_id))
    for site_id, value in items:
        db.add(BodyCircumference(measurement_id=measurement_id, body_site_id=site_id, value_cm=value))
    await db.flush()


# --- Mục tiêu ---
async def get_goal(db: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID) -> UserGoal | None:
    return await db.scalar(select(UserGoal).where(UserGoal.id == goal_id, UserGoal.user_id == user_id))


async def get_active_goal(db: AsyncSession, user_id: uuid.UUID) -> UserGoal | None:
    return await db.scalar(
        select(UserGoal).where(UserGoal.user_id == user_id, UserGoal.status == GoalStatus.ACTIVE)
    )


async def list_goals(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: GoalStatus | None,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[UserGoal]:
    stmt = select(UserGoal).where(UserGoal.user_id == user_id)
    if status is not None:
        stmt = stmt.where(UserGoal.status == status)
    if after is not None:
        stmt = stmt.where(tuple_(UserGoal.created_at, UserGoal.id) < tuple_(literal(after[0]), literal(after[1])))
    stmt = stmt.order_by(UserGoal.created_at.desc(), UserGoal.id.desc()).limit(limit)
    return list((await db.scalars(stmt)).all())


async def goal_types_by_id(db: AsyncSession, ids: set[int]) -> dict[int, FitnessGoalType]:
    if not ids:
        return {}
    rows = await db.scalars(select(FitnessGoalType).where(FitnessGoalType.id.in_(ids)))
    return {g.id: g for g in rows}
