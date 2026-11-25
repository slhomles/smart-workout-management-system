"""Model schema `body` — khớp database/postgresql/schemas/05_body.sql."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import pg_enum
from app.models.enums import Gender, GoalStatus, MeasurementSource

SCHEMA = "body"
NOW = text("now()")


class ActivityLevel(Base):
    __tablename__ = "activity_levels"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    multiplier: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)


class FitnessGoalType(Base):
    __tablename__ = "fitness_goal_types"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)


class BodySite(Base):
    __tablename__ = "body_sites"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)


class UserBodyProfile(Base):
    __tablename__ = "user_body_profiles"
    __table_args__ = {"schema": SCHEMA}

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("auth.users.id"), primary_key=True)
    gender: Mapped[Gender] = mapped_column(pg_enum(Gender, "gender", SCHEMA), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    activity_level_id: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("body.activity_levels.id"))
    experience_level_id: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)


class BodyMeasurement(Base):
    __tablename__ = "body_measurements"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("auth.users.id"), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    body_fat_pct: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    muscle_mass_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    source: Mapped[MeasurementSource] = mapped_column(
        pg_enum(MeasurementSource, "measurement_source", SCHEMA), nullable=False
    )
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)


class BodyCircumference(Base):
    __tablename__ = "body_circumferences"
    __table_args__ = {"schema": SCHEMA}

    measurement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("body.body_measurements.id", ondelete="CASCADE"), primary_key=True
    )
    body_site_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("body.body_sites.id"), primary_key=True)
    value_cm: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)


class UserGoal(Base):
    __tablename__ = "user_goals"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("auth.users.id"), nullable=False)
    goal_type_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("body.fitness_goal_types.id"), nullable=False)
    target_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    target_body_fat_pct: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    start_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=text("CURRENT_DATE"))
    target_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[GoalStatus] = mapped_column(pg_enum(GoalStatus, "goal_status", SCHEMA), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
