"""Schema Pydantic cho /body (chức năng 3). Giới hạn giá trị khớp CHECK trong 05_body.sql."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.models.enums import Gender, GoalStatus, MeasurementSource


# --- Danh mục ---
class ActivityLevelResponse(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    multiplier: float


class GoalTypeResponse(BaseModel):
    id: int
    code: str
    name: str
    description: str | None


class BodySiteResponse(BaseModel):
    id: int
    code: str
    name: str


# --- Hồ sơ thể chất ---
class BodyProfileResponse(BaseModel):
    gender: Gender
    date_of_birth: date | None
    height_cm: float | None
    activity_level_id: int | None
    experience_level_id: int | None
    updated_at: datetime | None = Field(None, description="NULL nếu user chưa tạo hồ sơ thể chất")


class ReplaceBodyProfileRequest(BaseModel):
    """PUT: phải gửi đủ mọi field (giá trị trống gửi null)."""

    gender: Gender
    date_of_birth: date | None = Field(..., ge=date(1900, 1, 1))
    height_cm: float | None = Field(..., ge=80, le=250)
    activity_level_id: int | None = Field(..., ge=1)
    experience_level_id: int | None = Field(..., ge=1)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "gender": "male",
                "date_of_birth": "2003-05-20",
                "height_cm": 172.0,
                "activity_level_id": 3,
                "experience_level_id": 1,
            }
        }
    )


# --- Lần đo ---
class CircumferenceInput(BaseModel):
    body_site_id: int = Field(..., ge=1)
    value_cm: float = Field(..., ge=5, le=300)


class CircumferenceResponse(BaseModel):
    body_site_id: int
    body_site_code: str
    body_site_name: str
    value_cm: float


class BodyMetricsSchema(BaseModel):
    """Chỉ số tính từ view body.v_body_metrics (không tính lại ở Python)."""

    age_years: int | None
    bmi: float | None
    bmi_category: Literal["underweight", "normal", "overweight", "obese"] | None
    lean_body_mass_kg: float | None
    bmr_kcal: int | None
    bmr_katch_mcardle_kcal: int | None
    tdee_kcal: int | None
    activity_level_code: str | None


def _check_circumferences(items: list[CircumferenceInput] | None) -> None:
    if items is not None and len({c.body_site_id for c in items}) != len(items):
        raise ValueError("Mỗi body_site_id chỉ được xuất hiện một lần")


class CreateBodyMeasurementRequest(BaseModel):
    measured_at: AwareDatetime | None = Field(None, description="Mặc định là thời điểm hiện tại")
    weight_kg: float = Field(..., ge=20, le=400)
    body_fat_pct: float | None = Field(None, ge=2, le=70)
    muscle_mass_kg: float | None = Field(None, gt=0)
    source: MeasurementSource = MeasurementSource.MANUAL
    note: str | None = Field(None, max_length=500)
    circumferences: list[CircumferenceInput] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _validate(self) -> "CreateBodyMeasurementRequest":
        if self.muscle_mass_kg is not None and self.muscle_mass_kg >= self.weight_kg:
            raise ValueError("muscle_mass_kg phải nhỏ hơn weight_kg")
        _check_circumferences(self.circumferences)
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "weight_kg": 70.0,
                "body_fat_pct": 18.4,
                "note": "Cân buổi sáng",
                "circumferences": [{"body_site_id": 4, "value_cm": 80.5}],
            }
        }
    )


class UpdateBodyMeasurementRequest(BaseModel):
    """PATCH: chỉ gửi field cần sửa. `circumferences` nếu gửi sẽ thay thế toàn bộ danh sách cũ."""

    measured_at: AwareDatetime | None = None
    weight_kg: float | None = Field(None, ge=20, le=400)
    body_fat_pct: float | None = Field(None, ge=2, le=70)
    muscle_mass_kg: float | None = Field(None, gt=0)
    note: str | None = Field(None, max_length=500)
    circumferences: list[CircumferenceInput] | None = Field(None, max_length=20)

    @model_validator(mode="after")
    def _validate(self) -> "UpdateBodyMeasurementRequest":
        _check_circumferences(self.circumferences)
        return self


class BodyMeasurementResponse(BaseModel):
    id: uuid.UUID
    measured_at: datetime
    weight_kg: float
    body_fat_pct: float | None
    muscle_mass_kg: float | None
    source: MeasurementSource
    note: str | None
    circumferences: list[CircumferenceResponse]
    metrics: BodyMetricsSchema
    created_at: datetime
    updated_at: datetime


# --- Mục tiêu ---
class GoalTypeSchema(BaseModel):
    id: int
    code: str
    name: str


class CreateUserGoalRequest(BaseModel):
    goal_type_id: int = Field(..., ge=1)
    target_weight_kg: float | None = Field(None, ge=20, le=400)
    target_body_fat_pct: float | None = Field(None, ge=2, le=70)
    start_date: date | None = Field(None, description="Mặc định là hôm nay")
    target_date: date | None = None

    @model_validator(mode="after")
    def _validate(self) -> "CreateUserGoalRequest":
        if self.target_date and self.start_date and self.target_date <= self.start_date:
            raise ValueError("target_date phải sau start_date")
        return self

    model_config = ConfigDict(
        json_schema_extra={"example": {"goal_type_id": 1, "target_weight_kg": 66.0, "target_date": "2027-03-01"}}
    )


class UpdateUserGoalRequest(BaseModel):
    """PATCH: đóng mục tiêu bằng status achieved/abandoned, hoặc sửa chỉ tiêu khi còn active."""

    status: Literal[GoalStatus.ACHIEVED, GoalStatus.ABANDONED] | None = None
    target_weight_kg: float | None = Field(None, ge=20, le=400)
    target_body_fat_pct: float | None = Field(None, ge=2, le=70)
    target_date: date | None = None


class UserGoalResponse(BaseModel):
    id: uuid.UUID
    goal_type: GoalTypeSchema
    target_weight_kg: float | None
    target_body_fat_pct: float | None
    start_date: date
    target_date: date | None
    status: GoalStatus
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime
