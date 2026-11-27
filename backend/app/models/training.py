"""Model buổi tập & set/rep — khớp database/postgresql/schemas/06_training.sql."""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import pg_enum
from app.models.enums import AddedVia, LogSource, PlanStatus, ScheduleStatus, SessionStatus, SetType

SCHEMA = "training"
NOW = text("now()")


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("auth.users.id"), nullable=False)
    scheduled_workout_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    name: Mapped[str | None] = mapped_column(String(150))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[SessionStatus] = mapped_column(pg_enum(SessionStatus, "session_status", SCHEMA), nullable=False)
    session_rpe: Mapped[float | None] = mapped_column(Numeric(3, 1, asdecimal=False))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SessionExercise(Base):
    __tablename__ = "session_exercises"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training.workout_sessions.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_exercise_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    order_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    added_via: Mapped[AddedVia] = mapped_column(pg_enum(AddedVia, "added_via", SCHEMA), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)


class ExerciseSet(Base):
    __tablename__ = "exercise_sets"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training.session_exercises.id", ondelete="CASCADE"), nullable=False
    )
    set_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    set_type: Mapped[SetType] = mapped_column(pg_enum(SetType, "set_type", SCHEMA), nullable=False)
    reps: Mapped[int | None] = mapped_column(SmallInteger)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(6, 2, asdecimal=False))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[float | None] = mapped_column(Numeric(8, 2, asdecimal=False))
    rpe: Mapped[float | None] = mapped_column(Numeric(3, 1, asdecimal=False))
    rest_seconds: Mapped[int | None] = mapped_column(SmallInteger)
    source: Mapped[LogSource] = mapped_column(pg_enum(LogSource, "log_source", SCHEMA), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)


class SetRepEvent(Base):
    __tablename__ = "set_rep_events"
    __table_args__ = {"schema": SCHEMA}

    set_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("training.exercise_sets.id", ondelete="CASCADE"), primary_key=True
    )
    rep_no: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    start_offset_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    eccentric_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    pause_bottom_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    concentric_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    pause_top_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    min_joint_angle_deg: Mapped[float | None] = mapped_column(Numeric(5, 2, asdecimal=False))
    max_joint_angle_deg: Mapped[float | None] = mapped_column(Numeric(5, 2, asdecimal=False))
    is_full_rom: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)


class WorkoutPlan(Base):
    __tablename__ = "workout_plans"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    # NULL = giáo án mẫu của hệ thống.
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE")
    )
    source_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training.workout_plans.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    goal_type_id: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("body.fitness_goal_types.id"))
    difficulty_level_id: Mapped[int | None] = mapped_column(SmallInteger)
    duration_weeks: Mapped[int | None] = mapped_column(SmallInteger)
    status: Mapped[PlanStatus] = mapped_column(
        pg_enum(PlanStatus, "plan_status", SCHEMA), nullable=False, server_default=text("'draft'")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkoutPlanDay(Base):
    __tablename__ = "workout_plan_days"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training.workout_plans.id", ondelete="CASCADE"), nullable=False
    )
    day_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)


class WorkoutPlanExercise(Base):
    __tablename__ = "workout_plan_exercises"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    plan_day_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training.workout_plan_days.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id: Mapped[int] = mapped_column(Integer, nullable=False)
    order_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    target_sets: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    target_reps_min: Mapped[int | None] = mapped_column(SmallInteger)
    target_reps_max: Mapped[int | None] = mapped_column(SmallInteger)
    target_duration_seconds: Mapped[int | None] = mapped_column(SmallInteger)
    target_weight_kg: Mapped[float | None] = mapped_column(Numeric(6, 2, asdecimal=False))
    target_rpe: Mapped[float | None] = mapped_column(Numeric(3, 1, asdecimal=False))
    rest_seconds: Mapped[int | None] = mapped_column(SmallInteger)
    tempo_eccentric_s: Mapped[int | None] = mapped_column(SmallInteger)
    tempo_pause_bottom_s: Mapped[int | None] = mapped_column(SmallInteger)
    tempo_concentric_s: Mapped[int | None] = mapped_column(SmallInteger)
    tempo_pause_top_s: Mapped[int | None] = mapped_column(SmallInteger)
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)


class ScheduledWorkout(Base):
    __tablename__ = "scheduled_workouts"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False
    )
    # NULL = buổi tự do (chỉ có title).
    plan_day_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training.workout_plan_days.id", ondelete="CASCADE")
    )
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[ScheduleStatus] = mapped_column(
        pg_enum(ScheduleStatus, "schedule_status", SCHEMA), nullable=False, server_default=text("'planned'")
    )
    recovery_warning_ack_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)


class RecoveryPrediction(Base):
    __tablename__ = "recovery_predictions"
    __table_args__ = {"schema": SCHEMA}

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training.workout_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    muscle_group_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    model_version: Mapped[str] = mapped_column(String(50), primary_key=True)
    fatigue_score: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False), nullable=False)
    recovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
