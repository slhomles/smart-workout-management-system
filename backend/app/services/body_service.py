"""Nghiệp vụ /body: hồ sơ thể chất, lần đo (+ số đo vòng), mục tiêu (chức năng 3)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, DataValidationError, NotFoundError
from app.crud import body as crud
from app.models.body import BodyMeasurement, UserBodyProfile, UserGoal
from app.models.enums import Gender, GoalStatus
from app.schemas.base import ErrorDetail, Page, Pagination, build_page, decode_keyset_cursor
from app.schemas.body import (
    ActivityLevelResponse,
    BodyMeasurementResponse,
    BodyMetricsSchema,
    BodyProfileResponse,
    BodySiteResponse,
    CircumferenceInput,
    CircumferenceResponse,
    CreateBodyMeasurementRequest,
    CreateUserGoalRequest,
    GoalTypeResponse,
    GoalTypeSchema,
    ReplaceBodyProfileRequest,
    UpdateBodyMeasurementRequest,
    UpdateUserGoalRequest,
    UserGoalResponse,
)


def _invalid(field: str, message: str) -> DataValidationError:
    return DataValidationError([ErrorDetail(field=field, message=message, code="invalid_reference")])


def _single_page(items: list[Any]) -> Page[Any]:
    return Page(data=items, pagination=Pagination(next_cursor=None, has_more=False))


# --- Danh mục ---
async def list_activity_levels(db: AsyncSession) -> Page[ActivityLevelResponse]:
    rows = await crud.list_activity_levels(db)
    return _single_page(
        [ActivityLevelResponse(id=r.id, code=r.code, name=r.name, description=r.description, multiplier=r.multiplier) for r in rows]
    )


async def list_goal_types(db: AsyncSession) -> Page[GoalTypeResponse]:
    rows = await crud.list_goal_types(db)
    return _single_page([GoalTypeResponse(id=r.id, code=r.code, name=r.name, description=r.description) for r in rows])


async def list_body_sites(db: AsyncSession) -> Page[BodySiteResponse]:
    rows = await crud.list_body_sites(db)
    return _single_page([BodySiteResponse(id=r.id, code=r.code, name=r.name) for r in rows])


# --- Hồ sơ thể chất ---
def _profile_response(profile: UserBodyProfile | None) -> BodyProfileResponse:
    if profile is None:
        return BodyProfileResponse(
            gender=Gender.UNSPECIFIED, date_of_birth=None, height_cm=None,
            activity_level_id=None, experience_level_id=None, updated_at=None,
        )
    return BodyProfileResponse(
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        height_cm=profile.height_cm,
        activity_level_id=profile.activity_level_id,
        experience_level_id=profile.experience_level_id,
        updated_at=profile.updated_at,
    )


async def get_profile(db: AsyncSession, user_id: uuid.UUID) -> BodyProfileResponse:
    return _profile_response(await crud.get_body_profile(db, user_id))


async def replace_profile(db: AsyncSession, user_id: uuid.UUID, req: ReplaceBodyProfileRequest) -> BodyProfileResponse:
    if req.activity_level_id and not await crud.existing_ids(db, "body.activity_levels", {req.activity_level_id}):
        raise _invalid("activity_level_id", "Mức vận động không tồn tại")
    if req.experience_level_id and not await crud.existing_ids(db, "catalog.difficulty_levels", {req.experience_level_id}):
        raise _invalid("experience_level_id", "Trình độ không tồn tại")
    if req.date_of_birth and req.date_of_birth > await crud.local_today(db, await crud.get_user_timezone(db, user_id)):
        raise _invalid("date_of_birth", "Ngày sinh không được ở tương lai")

    profile = await crud.get_body_profile(db, user_id)
    if profile is None:
        profile = UserBodyProfile(user_id=user_id)
        db.add(profile)
    profile.gender = req.gender
    profile.date_of_birth = req.date_of_birth
    profile.height_cm = req.height_cm
    profile.activity_level_id = req.activity_level_id
    profile.experience_level_id = req.experience_level_id
    await db.commit()
    await db.refresh(profile)
    return _profile_response(profile)


# --- Lần đo ---
def _measurement_response(row: Any, circumferences: list[Any]) -> BodyMeasurementResponse:
    return BodyMeasurementResponse(
        id=row["id"],
        measured_at=row["measured_at"],
        weight_kg=row["weight_kg"],
        body_fat_pct=row["body_fat_pct"],
        muscle_mass_kg=row["muscle_mass_kg"],
        source=row["source"],
        note=row["note"],
        circumferences=[CircumferenceResponse(**c) for c in circumferences],
        metrics=BodyMetricsSchema(
            age_years=row["age_years"],
            bmi=row["bmi"],
            bmi_category=row["bmi_category"],
            lean_body_mass_kg=row["lean_body_mass_kg"],
            bmr_kcal=row["bmr_kcal"],
            bmr_katch_mcardle_kcal=row["bmr_katch_mcardle_kcal"],
            tdee_kcal=row["tdee_kcal"],
            activity_level_code=row["activity_level_code"],
        ),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def _check_body_sites(db: AsyncSession, items: list[CircumferenceInput]) -> None:
    wanted = {c.body_site_id for c in items}
    missing = wanted - await crud.existing_ids(db, "body.body_sites", wanted)
    if missing:
        raise _invalid("circumferences", f"Vị trí đo không tồn tại: {sorted(missing)}")


async def get_measurement(db: AsyncSession, user_id: uuid.UUID, measurement_id: uuid.UUID) -> BodyMeasurementResponse:
    row = await crud.get_measurement_row(db, user_id, measurement_id)
    if row is None:
        raise NotFoundError("measurement_not_found", "Không tìm thấy lần đo")
    circ = await crud.circumferences_for(db, [row["id"]])
    return _measurement_response(row, circ[row["id"]])


async def list_measurements(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    from_: datetime | None,
    to: datetime | None,
    limit: int,
    cursor: str | None,
) -> Page[BodyMeasurementResponse]:
    rows = await crud.list_measurement_rows(
        db, user_id, from_=from_, to=to, after=decode_keyset_cursor(cursor, "measured_at"), limit=limit + 1
    )
    circ = await crud.circumferences_for(db, [r["id"] for r in rows[:limit]])
    return build_page(
        rows,
        limit,
        to_item=lambda r: _measurement_response(r, circ[r["id"]]),
        cursor_of=lambda r: {"measured_at": r["measured_at"].isoformat(), "id": str(r["id"])},
    )


async def create_measurement(
    db: AsyncSession, user_id: uuid.UUID, req: CreateBodyMeasurementRequest
) -> BodyMeasurementResponse:
    measured_at = req.measured_at or await crud.db_now(db)
    if await crud.measurement_exists_at(db, user_id, measured_at):
        raise ConflictError("measurement_already_exists", "Đã có lần đo tại thời điểm này")
    await _check_body_sites(db, req.circumferences)

    m = BodyMeasurement(
        user_id=user_id,
        measured_at=measured_at,
        weight_kg=req.weight_kg,
        body_fat_pct=req.body_fat_pct,
        muscle_mass_kg=req.muscle_mass_kg,
        source=req.source,
        note=req.note,
    )
    db.add(m)
    await db.flush()
    await crud.replace_circumferences(db, m.id, [(c.body_site_id, c.value_cm) for c in req.circumferences])
    await db.commit()
    return await get_measurement(db, user_id, m.id)


async def update_measurement(
    db: AsyncSession, user_id: uuid.UUID, measurement_id: uuid.UUID, req: UpdateBodyMeasurementRequest
) -> BodyMeasurementResponse:
    m = await db.get(BodyMeasurement, measurement_id)
    if m is None or m.user_id != user_id:
        raise NotFoundError("measurement_not_found", "Không tìm thấy lần đo")
    changes = req.model_dump(exclude_unset=True)
    if "weight_kg" in changes and changes["weight_kg"] is None:
        raise _invalid("weight_kg", "weight_kg không được để trống")
    if changes.get("measured_at") is not None and await crud.measurement_exists_at(
        db, user_id, changes["measured_at"], exclude_id=m.id
    ):
        raise ConflictError("measurement_already_exists", "Đã có lần đo tại thời điểm này")

    circumferences = changes.pop("circumferences", None)
    for field in ("measured_at", "weight_kg", "body_fat_pct", "muscle_mass_kg", "note"):
        if field in changes and not (field == "measured_at" and changes[field] is None):
            setattr(m, field, changes[field])
    if circumferences is not None:
        await _check_body_sites(db, req.circumferences or [])
        await crud.replace_circumferences(db, m.id, [(c.body_site_id, c.value_cm) for c in req.circumferences or []])
    await db.commit()
    return await get_measurement(db, user_id, m.id)


async def delete_measurement(db: AsyncSession, user_id: uuid.UUID, measurement_id: uuid.UUID) -> None:
    m = await db.get(BodyMeasurement, measurement_id)
    if m is None or m.user_id != user_id:
        raise NotFoundError("measurement_not_found", "Không tìm thấy lần đo")
    await db.delete(m)  # số đo vòng xoá theo ON DELETE CASCADE
    await db.commit()


# --- Mục tiêu ---
async def _goal_responses(db: AsyncSession, goals: list[UserGoal]) -> list[UserGoalResponse]:
    types = await crud.goal_types_by_id(db, {g.goal_type_id for g in goals})
    return [
        UserGoalResponse(
            id=g.id,
            goal_type=GoalTypeSchema(
                id=g.goal_type_id, code=types[g.goal_type_id].code, name=types[g.goal_type_id].name
            ),
            target_weight_kg=g.target_weight_kg,
            target_body_fat_pct=g.target_body_fat_pct,
            start_date=g.start_date,
            target_date=g.target_date,
            status=g.status,
            closed_at=g.closed_at,
            created_at=g.created_at,
            updated_at=g.updated_at,
        )
        for g in goals
    ]


async def goal_response(db: AsyncSession, goal: UserGoal) -> UserGoalResponse:
    return (await _goal_responses(db, [goal]))[0]


async def get_goal(db: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID) -> UserGoalResponse:
    goal = await crud.get_goal(db, user_id, goal_id)
    if goal is None:
        raise NotFoundError("goal_not_found", "Không tìm thấy mục tiêu")
    return await goal_response(db, goal)


async def list_goals(
    db: AsyncSession, user_id: uuid.UUID, *, status: GoalStatus | None, limit: int, cursor: str | None
) -> Page[UserGoalResponse]:
    goals = await crud.list_goals(db, user_id, status=status, after=decode_keyset_cursor(cursor, "created_at"), limit=limit + 1)
    responses = {r.id: r for r in await _goal_responses(db, goals[:limit])}
    return build_page(
        goals,
        limit,
        to_item=lambda g: responses[g.id],
        cursor_of=lambda g: {"created_at": g.created_at.isoformat(), "id": str(g.id)},
    )


async def create_goal(db: AsyncSession, user_id: uuid.UUID, req: CreateUserGoalRequest) -> UserGoalResponse:
    if not await crud.existing_ids(db, "body.fitness_goal_types", {req.goal_type_id}):
        raise _invalid("goal_type_id", "Loại mục tiêu không tồn tại")
    if await crud.get_active_goal(db, user_id) is not None:
        raise ConflictError("active_goal_already_exists", "Bạn đang có một mục tiêu chưa hoàn thành")
    start_date = req.start_date or await crud.local_today(db, await crud.get_user_timezone(db, user_id))
    if req.target_date and req.target_date <= start_date:
        raise _invalid("target_date", "target_date phải sau start_date")

    goal = UserGoal(
        user_id=user_id,
        goal_type_id=req.goal_type_id,
        target_weight_kg=req.target_weight_kg,
        target_body_fat_pct=req.target_body_fat_pct,
        start_date=start_date,
        target_date=req.target_date,
        status=GoalStatus.ACTIVE,
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return await goal_response(db, goal)


async def update_goal(
    db: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID, req: UpdateUserGoalRequest
) -> UserGoalResponse:
    goal = await crud.get_goal(db, user_id, goal_id)
    if goal is None:
        raise NotFoundError("goal_not_found", "Không tìm thấy mục tiêu")
    changes = req.model_dump(exclude_unset=True)
    if changes and goal.status != GoalStatus.ACTIVE:
        raise _invalid("status", "Mục tiêu đã đóng, không thể sửa")
    if "target_date" in changes and changes["target_date"] and changes["target_date"] <= goal.start_date:
        raise _invalid("target_date", "target_date phải sau start_date")

    for field in ("target_weight_kg", "target_body_fat_pct", "target_date"):
        if field in changes:
            setattr(goal, field, changes[field])
    if changes.get("status") is not None:
        goal.status = changes["status"]
        goal.closed_at = await crud.db_now(db)
    await db.commit()
    await db.refresh(goal)
    return await goal_response(db, goal)
