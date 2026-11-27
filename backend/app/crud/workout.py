"""Truy vấn buổi tập / hiệp / rep. Volume, 1RM, tempo đọc từ view training.v_set_metrics, v_set_tempo."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SessionStatus
from app.models.training import ExerciseSet, SessionExercise, SetRepEvent, WorkoutSession


async def get_session(
    db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID, *, for_update: bool = False
) -> WorkoutSession | None:
    stmt = select(WorkoutSession).where(
        WorkoutSession.id == session_id, WorkoutSession.user_id == user_id, WorkoutSession.deleted_at.is_(None)
    )
    if for_update:
        stmt = stmt.with_for_update()
    return await db.scalar(stmt)


async def has_session_in_progress(db: AsyncSession, user_id: uuid.UUID) -> bool:
    found = await db.scalar(
        select(WorkoutSession.id).where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.status == SessionStatus.IN_PROGRESS,
            WorkoutSession.deleted_at.is_(None),
        )
    )
    return found is not None


_SUMMARY_SELECT = """
SELECT session_id AS id, name, status, started_at, ended_at, duration_minutes,
       exercise_count, completed_set_count, total_reps, total_volume_kg, est_calories_kcal
FROM training.v_session_summary
WHERE user_id = :user_id
"""


async def session_summary(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID) -> Any | None:
    sql = _SUMMARY_SELECT + " AND session_id = :id"
    return (await db.execute(text(sql), {"user_id": user_id, "id": session_id})).mappings().first()


async def list_session_summaries(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: SessionStatus | None,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[Any]:
    sql = _SUMMARY_SELECT
    params: dict[str, Any] = {"user_id": user_id, "limit": limit}
    if status is not None:
        sql += " AND status = CAST(:status AS training.session_status)"
        params["status"] = status.value
    if after is not None:
        sql += " AND (started_at, session_id) < (:c_at, :c_id)"
        params["c_at"], params["c_id"] = after
    sql += " ORDER BY started_at DESC, session_id DESC LIMIT :limit"
    return list((await db.execute(text(sql), params)).mappings().all())


async def get_published_exercise(db: AsyncSession, exercise_id: int) -> Any | None:
    """Đọc bài tập ở module Catalog (chỉ đọc): phải published và chưa xoá."""
    sql = """
    SELECT id, slug, name, supports_ai_tracking FROM catalog.exercises
    WHERE id = :id AND status = 'published' AND deleted_at IS NULL
    """
    return (await db.execute(text(sql), {"id": exercise_id})).mappings().first()


async def session_exercises(db: AsyncSession, session_id: uuid.UUID) -> list[Any]:
    sql = """
    SELECT se.id, se.order_no, se.added_via, se.notes,
           e.id AS exercise_id, e.slug, e.name, e.supports_ai_tracking
    FROM training.session_exercises se
    JOIN catalog.exercises e ON e.id = se.exercise_id
    WHERE se.session_id = :session_id
    ORDER BY se.order_no
    """
    return list((await db.execute(text(sql), {"session_id": session_id})).mappings().all())


async def get_session_exercise(
    db: AsyncSession, session_id: uuid.UUID, session_exercise_id: uuid.UUID
) -> SessionExercise | None:
    return await db.scalar(
        select(SessionExercise).where(
            SessionExercise.id == session_exercise_id, SessionExercise.session_id == session_id
        )
    )


async def next_order_no(db: AsyncSession, session_id: uuid.UUID) -> int:
    current = await db.scalar(
        select(func.max(SessionExercise.order_no)).where(SessionExercise.session_id == session_id)
    )
    return (current or 0) + 1


async def next_set_no(db: AsyncSession, session_exercise_id: uuid.UUID) -> int:
    current = await db.scalar(
        select(func.max(ExerciseSet.set_no)).where(ExerciseSet.session_exercise_id == session_exercise_id)
    )
    return (current or 0) + 1


async def get_set(db: AsyncSession, session_exercise_id: uuid.UUID, set_id: int) -> ExerciseSet | None:
    return await db.scalar(
        select(ExerciseSet).where(ExerciseSet.id == set_id, ExerciseSet.session_exercise_id == session_exercise_id)
    )


_SET_SELECT = """
SELECT es.id, es.session_exercise_id, es.set_no, es.set_type, es.reps, es.weight_kg, es.duration_seconds,
       es.distance_m, es.rpe, es.rest_seconds, es.source, es.completed_at,
       m.volume_kg, m.est_1rm_kg,
       t.rep_count, t.avg_eccentric_ms, t.avg_pause_bottom_ms, t.avg_concentric_ms, t.avg_pause_top_ms,
       t.time_under_tension_ms, t.full_rom_pct
FROM training.exercise_sets es
JOIN training.v_set_metrics m ON m.set_id = es.id
LEFT JOIN training.v_set_tempo t ON t.set_id = es.id
"""


async def set_rows(db: AsyncSession, session_exercise_ids: list[uuid.UUID]) -> list[Any]:
    if not session_exercise_ids:
        return []
    sql = _SET_SELECT + " WHERE es.session_exercise_id = ANY(:ids) ORDER BY es.session_exercise_id, es.set_no"
    return list((await db.execute(text(sql), {"ids": session_exercise_ids})).mappings().all())


async def set_row(db: AsyncSession, set_id: int) -> Any | None:
    return (await db.execute(text(_SET_SELECT + " WHERE es.id = :id"), {"id": set_id})).mappings().first()


async def rep_events(db: AsyncSession, set_id: int) -> list[SetRepEvent]:
    rows = await db.scalars(select(SetRepEvent).where(SetRepEvent.set_id == set_id).order_by(SetRepEvent.rep_no))
    return list(rows.all())


# --- Dành cho module AI (qua services/workout_ai_service.py) ---
_OWNED_SET_CONTEXT_SQL = """
SELECT es.id AS set_id, es.session_exercise_id, se.session_id,
       e.id AS exercise_id, e.name AS exercise_name, e.supports_ai_tracking
FROM training.exercise_sets es
JOIN training.session_exercises se ON se.id = es.session_exercise_id
JOIN training.workout_sessions s ON s.id = se.session_id
JOIN catalog.exercises e ON e.id = se.exercise_id
WHERE es.id = :set_id AND s.user_id = :user_id AND s.deleted_at IS NULL
"""


async def owned_set_context(db: AsyncSession, user_id: uuid.UUID, set_id: int) -> Any | None:
    """Hiệp của user (buổi chưa xoá mềm) kèm buổi và bài tập; None nếu không có/không thuộc user."""
    params = {"set_id": set_id, "user_id": user_id}
    return (await db.execute(text(_OWNED_SET_CONTEXT_SQL), params)).mappings().first()


async def lock_set(db: AsyncSession, set_id: int) -> ExerciseSet | None:
    """Khoá dòng hiệp (`SELECT … FOR UPDATE`) để ghi rep AI; None nếu không có."""
    # populate_existing: hiệp có thể còn trong identity map với giá trị cũ (expire_on_commit=False).
    stmt = (
        select(ExerciseSet)
        .where(ExerciseSet.id == set_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return await db.scalar(stmt)


async def delete_rep_events(db: AsyncSession, set_id: int) -> None:
    """Xoá mọi rep của hiệp; delete ORM để identity map không giữ rep cũ trùng khoá (set_id, rep_no)."""
    await db.execute(delete(SetRepEvent).where(SetRepEvent.set_id == set_id))
