"""Schema Pydantic cho /scheduled-workouts (chức năng 2: Workout Routine).

Bộ field khớp bảng training.scheduled_workouts (06_training.sql); `workout_session_id` và
`is_completed` suy ra từ buổi tập gắn với lịch (doc 05 §2.3).
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic.json_schema import JsonDict

from app.models.enums import ScheduleStatus


def _blank_to_none(value: str | None) -> str | None:
    """Chuỗi chỉ có khoảng trắng (đã strip) coi như không gửi."""
    return value or None


# Strip rồi mới đo độ dài, khớp varchar(150)/varchar(500) của bảng.
_Title = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=150)] | None, AfterValidator(_blank_to_none)
]
_Notes = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None, AfterValidator(_blank_to_none)
]

# Ví dụ lấy từ seed: lịch "Tập bù Push" của demo, buổi 1 của giáo án "PPL của An".
_EXAMPLE_PLAN_DAY: JsonDict = {
    "id": "0b8d3c3e-1f4a-4c6e-8f0d-5a7b9c1d2e30",
    "plan_id": "dd1b5d27-91cb-46bf-be5a-cefb66fcaaf9",
    "plan_name": "PPL của An",
    "day_no": 1,
    "name": "Push – Ngực/Vai/Tay sau",
}
_EXAMPLE_SCHEDULE: JsonDict = {
    "id": "3f6c2a8e-7d41-4b2a-9c3e-1a5b7d9e0f12",
    "scheduled_date": "2026-11-28",
    "title": "Tập bù Push",
    "notes": None,
    "status": "planned",
    "plan_day": _EXAMPLE_PLAN_DAY,
    "recovery_warning_ack_at": "2026-11-27T04:05:56.505408Z",
    "workout_session_id": None,
    "is_completed": False,
    "created_at": "2026-11-27T04:05:56.505408Z",
}
_EXAMPLE_CREATE_SCHEDULE: JsonDict = {
    "scheduled_date": "2026-11-29",
    "plan_day_id": "0b8d3c3e-1f4a-4c6e-8f0d-5a7b9c1d2e30",
    "title": None,
    "notes": None,
    "acknowledge_recovery_warning": False,
}


_QUERY_ALIASES = {"from_date": "from", "to_date": "to"}


class ScheduledWorkoutListQuery(BaseModel):
    """Query của `GET /scheduled-workouts`, gom vào một model (coding-standards §1)."""

    # `from` là từ khoá Python nên field mang tên khác; client vẫn gửi `from`.
    from_date: date | None = Field(None, alias="from", description="Từ ngày (YYYY-MM-DD), tính cả ngày này")
    to_date: date | None = Field(None, alias="to", description="Đến ngày (YYYY-MM-DD), tính cả ngày này")
    status: ScheduleStatus | None = Field(None, description="Lọc theo trạng thái lịch")
    limit: int = Field(20, ge=1, le=100)
    cursor: str | None = Field(None, description="`next_cursor` của trang trước")

    @model_validator(mode="before")
    @classmethod
    def _use_aliases(cls, data: Any) -> Any:
        """FastAPI 0.115 đưa query vào model theo tên field (`from_date`), không theo alias.

        Đổi về alias để Pydantic đọc qua alias và lỗi báo đúng tên tham số client gửi (`from`, `to`).
        """
        if isinstance(data, dict):
            return {_QUERY_ALIASES.get(key, key): value for key, value in data.items()}
        return data


class ScheduledPlanDaySchema(BaseModel):
    """Buổi giáo án gắn với lịch (của user hoặc giáo án mẫu), kèm tên giáo án."""

    id: uuid.UUID
    plan_id: uuid.UUID
    plan_name: str
    day_no: int
    name: str

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"example": _EXAMPLE_PLAN_DAY})


class ScheduledWorkoutResponse(BaseModel):
    """Một lịch tập; `is_completed` = buổi tập gắn với lịch đã `completed`."""

    id: uuid.UUID
    scheduled_date: date
    title: str | None
    notes: str | None
    status: ScheduleStatus
    plan_day: ScheduledPlanDaySchema | None = Field(..., description="null = buổi tự do")
    recovery_warning_ack_at: datetime | None = Field(
        ..., description="Lúc user xác nhận vẫn tập dù nhóm cơ chưa hồi phục"
    )
    workout_session_id: uuid.UUID | None = Field(..., description="Buổi tập (chưa xoá) thực hiện lịch này")
    is_completed: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"example": _EXAMPLE_SCHEDULE})


class CreateScheduledWorkoutRequest(BaseModel):
    """Body `POST /scheduled-workouts`: cần `plan_day_id` hoặc `title` (buổi tự do)."""

    scheduled_date: date = Field(..., description="Ngày tập (YYYY-MM-DD), không trước hôm nay theo múi giờ user")
    plan_day_id: uuid.UUID | None = Field(None, description="Buổi giáo án của user hoặc của giáo án mẫu")
    title: _Title = Field(None, description="Tiêu đề buổi tự do (hoặc ghi đè tên buổi giáo án)")
    notes: _Notes = None
    acknowledge_recovery_warning: bool = Field(
        False, description="Xác nhận vẫn xếp lịch dù nhóm cơ đích chưa hồi phục"
    )

    model_config = ConfigDict(json_schema_extra={"example": _EXAMPLE_CREATE_SCHEDULE})
