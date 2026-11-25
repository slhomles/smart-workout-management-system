"""Schema Pydantic cho /dashboard (chức năng 3). Không có calo nạp vào: Food Control ngoài phạm vi (doc 05 §6.3)."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.body import UserGoalResponse

TrendRange = Literal["week", "month", "3months"]


class LatestMetricsSchema(BaseModel):
    measurement_id: uuid.UUID
    measured_at: datetime
    weight_kg: float
    body_fat_pct: float | None
    bmi: float | None
    bmi_category: str | None
    bmr_kcal: int | None
    tdee_kcal: int | None


class TodaySummarySchema(BaseModel):
    sessions_completed: int
    est_calories_burned_kcal: int
    total_volume_kg: float
    duration_minutes: float
    has_session_in_progress: bool


class WeekProgressSchema(BaseModel):
    week_start: date
    planned_count: int
    completed_planned_count: int
    skipped_count: int
    adherence_pct: float | None
    sessions_completed: int


class DashboardResponse(BaseModel):
    date: date
    timezone: str
    latest_metrics: LatestMetricsSchema | None
    active_goal: UserGoalResponse | None
    today: TodaySummarySchema
    this_week: WeekProgressSchema
    is_plateau: bool


class WeightTrendPointSchema(BaseModel):
    week_start: date
    avg_weight_kg: float | None
    min_weight_kg: float | None
    max_weight_kg: float | None
    avg_body_fat_pct: float | None
    measurement_count: int
    change_kg: float | None
    is_plateau: bool
    sessions_completed: int
    est_calories_burned_kcal: int


class WeightTrendResponse(BaseModel):
    range: TrendRange
    from_date: date
    to_date: date
    points: list[WeightTrendPointSchema]
    is_plateau: bool
