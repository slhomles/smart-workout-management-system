"""Schema Pydantic cho Progress Gallery: /progress-photos (chức năng 4)."""

import uuid
from datetime import date, datetime, timezone

from fastapi import Form
from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator

from app.models.enums import CaptureSource, JobStatus, PhotoAngle

NOTE_MAX_LENGTH = 500  # khớp media.progress_photos.note varchar(500)


class UploadProgressPhotoForm:
    """Các field form của `POST /progress-photos` (gom lại để handler ≤ 4 tham số).

    Dùng làm dependency (`Depends()`): FastAPI đọc từng tham số `Form(...)` của `__init__`, lỗi
    validation báo đúng tên field (`angle`, `capture_source`, `taken_at`, `note`).
    """

    def __init__(
        self,
        angle: PhotoAngle = Form(..., description="Góc chụp: front / side / back"),
        capture_source: CaptureSource = Form(CaptureSource.CAMERA, description="camera / library"),
        taken_at: AwareDatetime | None = Form(
            None, description="Thời điểm chụp, ISO-8601 có múi giờ; mặc định là giờ server"
        ),
        note: str | None = Form(None, max_length=NOTE_MAX_LENGTH, description="Ghi chú, ≤ 500 ký tự"),
    ) -> None:
        self.angle = angle
        self.capture_source = capture_source
        self.taken_at = taken_at
        # Chuỗi chỉ toàn khoảng trắng không mang thông tin → lưu null thay vì chuỗi rỗng.
        self.note = (note.strip() or None) if note is not None else None


class ProgressPhotoResponse(BaseModel):
    """Một ảnh tiến độ kèm ngày chụp (theo múi giờ user) và số đo gần nhất tại thời điểm chụp."""

    id: uuid.UUID
    angle: PhotoAngle
    capture_source: CaptureSource
    taken_at: datetime
    taken_date: date
    note: str | None
    processing_status: JobStatus
    original_media_id: uuid.UUID
    watermarked_media_id: uuid.UUID | None
    thumbnail_media_id: uuid.UUID | None
    measurement_id: uuid.UUID | None
    measured_at: datetime | None
    weight_kg: float | None
    body_fat_pct: float | None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "6f1c2b9e-3d4a-4f5b-8c7d-9e0a1b2c3d4e",
                "angle": "front",
                "capture_source": "camera",
                "taken_at": "2026-11-26T01:00:00Z",
                "taken_date": "2026-11-26",
                "note": "Tuần 6",
                "processing_status": "completed",
                "original_media_id": "0b7e6a52-1f3c-4d8e-9a2b-3c4d5e6f7a8b",
                "watermarked_media_id": "1c8f7b63-2a4d-4e9f-8b3c-4d5e6f7a8b9c",
                "thumbnail_media_id": "2d9a8c74-3b5e-4fa0-9c4d-5e6f7a8b9cad",
                "measurement_id": "3eab9d85-4c6f-40b1-8d5e-6f7a8b9cadbe",
                "measured_at": "2026-11-25T23:30:00Z",
                "weight_kg": 70.0,
                "body_fat_pct": 18.4,
                "created_at": "2026-11-26T01:00:05Z",
            }
        },
    )

    @field_validator("taken_at", "measured_at", "created_at")
    @classmethod
    def _as_utc(cls, value: datetime | None) -> datetime | None:
        # Driver trả theo múi giờ của phiên DB; contract yêu cầu UTC hậu tố `Z` (Claude_api_respone §2).
        return value.astimezone(timezone.utc) if value is not None else None
