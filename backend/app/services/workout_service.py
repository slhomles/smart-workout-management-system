"""
Nghiệp vụ /workout-sessions (chức năng 6): buổi tập, bài trong buổi, hiệp kèm rep từ FSM.
Khi kết thúc hiệp AI, app gửi rep_events; server lưu từng rep vào set_rep_events, tự điền
reps = số rep (nếu không gửi) và trả tempo trung bình/TUT từ training.v_set_tempo.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.crud import body as body_crud
from app.crud import workout as crud
from app.models.enums import LogSource, SessionStatus
from app.models.training import ExerciseSet, SessionExercise, SetRepEvent, WorkoutSession
from app.schemas.base import Page, build_page, decode_keyset_cursor
from app.schemas.workout import (
    AddSessionExerciseRequest,
    CreateExerciseSetRequest,
    CreateWorkoutSessionRequest,
    ExerciseRefSchema,
    ExerciseSetDetailResponse,
    ExerciseSetResponse,
    FinishWorkoutSessionRequest,
    RepEventResponse,
    SessionExerciseResponse,
    SetTempoSchema,
    UpdateExerciseSetRequest,
    WorkoutSessionResponse,
    WorkoutSessionSummaryResponse,
)
from app.services import permission_service

_SESSION_NOT_FOUND = ("workout_session_not_found", "Không tìm thấy buổi tập")


# --- Chuyển đổi ---
def _set_response(row: Any) -> ExerciseSetResponse:
    tempo = None
    if row["rep_count"] is not None:
        tempo = SetTempoSchema(
            rep_count=row["rep_count"],
            avg_eccentric_ms=row["avg_eccentric_ms"],
            avg_pause_bottom_ms=row["avg_pause_bottom_ms"],
            avg_concentric_ms=row["avg_concentric_ms"],
            avg_pause_top_ms=row["avg_pause_top_ms"],
            time_under_tension_ms=row["time_under_tension_ms"],
            full_rom_pct=row["full_rom_pct"],
        )
    return ExerciseSetResponse(
        id=row["id"],
        set_no=row["set_no"],
        set_type=row["set_type"],
        reps=row["reps"],
        weight_kg=row["weight_kg"],
        duration_seconds=row["duration_seconds"],
        distance_m=row["distance_m"],
        rpe=row["rpe"],
        rest_seconds=row["rest_seconds"],
        source=row["source"],
        completed_at=row["completed_at"],
        volume_kg=row["volume_kg"],
        est_1rm_kg=row["est_1rm_kg"],
        tempo=tempo,
    )


def _summary_response(row: Any) -> WorkoutSessionSummaryResponse:
    return WorkoutSessionSummaryResponse(**row)


async def _exercise_responses(db: AsyncSession, session_id: uuid.UUID) -> list[SessionExerciseResponse]:
    exercises = await crud.session_exercises(db, session_id)
    sets: dict[uuid.UUID, list[ExerciseSetResponse]] = {e["id"]: [] for e in exercises}
    for row in await crud.set_rows(db, list(sets)):
        sets[row["session_exercise_id"]].append(_set_response(row))
    return [
        SessionExerciseResponse(
            id=e["id"],
            exercise=ExerciseRefSchema(
                id=e["exercise_id"], slug=e["slug"], name=e["name"], supports_ai_tracking=e["supports_ai_tracking"]
            ),
            order_no=e["order_no"],
            added_via=e["added_via"],
            notes=e["notes"],
            sets=sets[e["id"]],
        )
        for e in exercises
    ]


# --- Kiểm tra sở hữu & trạng thái ---
async def _owned_session(
    db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID, *, in_progress: bool = False
) -> WorkoutSession:
    session = await crud.get_session(db, user_id, session_id, for_update=in_progress)
    if session is None:
        raise NotFoundError(*_SESSION_NOT_FOUND)
    if in_progress and session.status != SessionStatus.IN_PROGRESS:
        raise ConflictError("session_not_in_progress", "Buổi tập đã kết thúc, không thể thay đổi")
    return session


async def _owned_session_exercise(
    db: AsyncSession, session: WorkoutSession, session_exercise_id: uuid.UUID
) -> SessionExercise:
    se = await crud.get_session_exercise(db, session.id, session_exercise_id)
    if se is None:
        raise NotFoundError("session_exercise_not_found", "Không tìm thấy bài tập trong buổi")
    return se


async def _owned_set(db: AsyncSession, se: SessionExercise, set_id: int) -> ExerciseSet:
    exercise_set = await crud.get_set(db, se.id, set_id)
    if exercise_set is None:
        raise NotFoundError("exercise_set_not_found", "Không tìm thấy hiệp tập")
    return exercise_set


# --- Buổi tập ---
async def get_session(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID) -> WorkoutSessionResponse:
    session = await _owned_session(db, user_id, session_id)
    summary = await crud.session_summary(db, user_id, session.id)
    if summary is None:  # view lọc cùng điều kiện với _owned_session; chỉ xảy ra nếu buổi vừa bị xoá mềm
        raise NotFoundError(*_SESSION_NOT_FOUND)
    return WorkoutSessionResponse(
        **summary,
        session_rpe=session.session_rpe,
        notes=session.notes,
        exercises=await _exercise_responses(db, session.id),
    )


async def list_sessions(
    db: AsyncSession, user_id: uuid.UUID, *, status: SessionStatus | None, limit: int, cursor: str | None
) -> Page[WorkoutSessionSummaryResponse]:
    rows = await crud.list_session_summaries(
        db, user_id, status=status, after=decode_keyset_cursor(cursor, "started_at"), limit=limit + 1
    )
    return build_page(
        rows,
        limit,
        to_item=_summary_response,
        cursor_of=lambda r: {"started_at": r["started_at"].isoformat(), "id": str(r["id"])},
    )


async def start_session(
    db: AsyncSession, user_id: uuid.UUID, req: CreateWorkoutSessionRequest
) -> WorkoutSessionResponse:
    if await crud.has_session_in_progress(db, user_id):
        raise ConflictError("session_already_in_progress", "Bạn đang có một buổi tập chưa kết thúc")
    session = WorkoutSession(user_id=user_id, name=req.name, notes=req.notes, status=SessionStatus.IN_PROGRESS)
    db.add(session)
    await db.commit()
    return await get_session(db, user_id, session.id)


async def finish_session(
    db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID, req: FinishWorkoutSessionRequest
) -> WorkoutSessionResponse:
    session = await _owned_session(db, user_id, session_id, in_progress=True)
    session.status = req.status
    session.ended_at = await body_crud.db_now(db)
    if req.session_rpe is not None:
        session.session_rpe = req.session_rpe
    if req.notes is not None:
        session.notes = req.notes
    await db.commit()
    return await get_session(db, user_id, session.id)


# --- Bài trong buổi ---
async def add_exercise(
    db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID, req: AddSessionExerciseRequest
) -> SessionExerciseResponse:
    session = await _owned_session(db, user_id, session_id, in_progress=True)
    exercise = await crud.get_published_exercise(db, req.exercise_id)
    if exercise is None:
        raise NotFoundError("exercise_not_found", "Không tìm thấy bài tập")
    se = SessionExercise(
        session_id=session.id,
        exercise_id=exercise["id"],
        order_no=await crud.next_order_no(db, session.id),
        added_via=req.added_via,
        notes=req.notes,
    )
    db.add(se)
    await db.commit()
    return next(e for e in await _exercise_responses(db, session.id) if e.id == se.id)


# --- Hiệp ---
async def _set_detail(db: AsyncSession, set_id: int) -> ExerciseSetDetailResponse:
    base = _set_response(await crud.set_row(db, set_id))
    events = [RepEventResponse.model_validate(e, from_attributes=True) for e in await crud.rep_events(db, set_id)]
    return ExerciseSetDetailResponse(**base.model_dump(), rep_events=events)


async def _require_ai_permission(db: AsyncSession, user_id: uuid.UUID) -> None:
    if "ai:use" not in await permission_service.get_permissions(db, user_id):
        raise PermissionDeniedError(message="Bạn không có quyền dùng tính năng AI đếm rep")


async def create_set(
    db: AsyncSession,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    session_exercise_id: uuid.UUID,
    req: CreateExerciseSetRequest,
) -> ExerciseSetDetailResponse:
    if req.source != LogSource.MANUAL:
        await _require_ai_permission(db, user_id)
    session = await _owned_session(db, user_id, session_id, in_progress=True)
    se = await _owned_session_exercise(db, session, session_exercise_id)

    exercise_set = ExerciseSet(
        session_exercise_id=se.id,
        set_no=await crud.next_set_no(db, se.id),
        set_type=req.set_type,
        reps=req.reps if req.reps is not None else (len(req.rep_events) if req.rep_events else None),
        weight_kg=req.weight_kg,
        duration_seconds=req.duration_seconds,
        distance_m=req.distance_m,
        rpe=req.rpe,
        rest_seconds=req.rest_seconds,
        source=req.source,
        completed_at=req.completed_at or await body_crud.db_now(db),
    )
    db.add(exercise_set)
    await db.flush()
    for event in req.rep_events:
        db.add(SetRepEvent(set_id=exercise_set.id, **event.model_dump()))
    await db.commit()
    return await _set_detail(db, exercise_set.id)


async def get_set(
    db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID, session_exercise_id: uuid.UUID, set_id: int
) -> ExerciseSetDetailResponse:
    session = await _owned_session(db, user_id, session_id)
    se = await _owned_session_exercise(db, session, session_exercise_id)
    await _owned_set(db, se, set_id)
    return await _set_detail(db, set_id)


async def update_set(
    db: AsyncSession,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    session_exercise_id: uuid.UUID,
    set_id: int,
    req: UpdateExerciseSetRequest,
) -> ExerciseSetDetailResponse:
    session = await _owned_session(db, user_id, session_id, in_progress=True)
    se = await _owned_session_exercise(db, session, session_exercise_id)
    exercise_set = await _owned_set(db, se, set_id)
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(exercise_set, field, value)
    await db.commit()  # vi phạm ck_exercise_sets_* (vd: xoá hết chỉ số) → 422 qua handler IntegrityError
    return await _set_detail(db, set_id)


async def delete_set(
    db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID, session_exercise_id: uuid.UUID, set_id: int
) -> None:
    session = await _owned_session(db, user_id, session_id, in_progress=True)
    se = await _owned_session_exercise(db, session, session_exercise_id)
    exercise_set = await _owned_set(db, se, set_id)
    await db.delete(exercise_set)  # rep events xoá theo ON DELETE CASCADE
    await db.commit()
