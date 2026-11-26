"""Schema Pydantic cho /reports — xuất thẻ báo cáo tuần/tháng (chức năng 3, bước 5)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ReportType


class CreateReportExportRequest(BaseModel):
    report_type: ReportType = ReportType.WEEKLY_SUMMARY
    period_start: date = Field(..., description="Thứ Hai đầu tuần (weekly_summary) hoặc ngày 1 (monthly_summary)")

    model_config = ConfigDict(
        json_schema_extra={"example": {"report_type": "weekly_summary", "period_start": "2026-11-16"}}
    )


class ReportSummarySchema(BaseModel):
    sessions_completed: int
    duration_minutes: float
    total_volume_kg: float
    est_calories_burned_kcal: int
    completed_set_count: int
    total_reps: int
    planned_count: int
    completed_planned_count: int
    adherence_pct: float | None
    avg_weight_kg: float | None
    weight_change_kg: float | None


class ReportExportResponse(BaseModel):
    id: uuid.UUID
    report_type: ReportType
    period_start: date
    period_end: date = Field(..., description="Ngày đầu kỳ kế tiếp (không bao gồm) = period_start + kỳ")
    media_id: uuid.UUID
    image_url: str = Field(..., description="Đường dẫn API tải ảnh PNG (cần Bearer token)")
    summary: ReportSummarySchema
    created_at: datetime
