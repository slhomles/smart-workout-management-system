"""Schema Pydantic cho Progress Gallery: /progress-photos, /photo-comparisons (chức năng 4)."""

import uuid
from datetime import date, datetime, timezone
from typing import Any

from fastapi import Form, Query
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.models.enums import CaptureSource, JobStatus, PhotoAngle

NOTE_MAX_LENGTH = 500  # khớp media.progress_photos.note varchar(500)
TITLE_MAX_LENGTH = 100  # khớp media.photo_comparisons.title varchar(100)


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


class ListProgressPhotosQuery:
    """Query của `GET /progress-photos` (gom lại để service ≤ 4 tham số, coding-standards §1).

    Dùng làm dependency (`Depends()`): lỗi validation báo đúng tên field (`angle`, `limit`, `cursor`).
    """

    def __init__(
        self,
        angle: PhotoAngle | None = Query(None, description="Lọc theo góc chụp: front / side / back"),
        limit: int = Query(20, ge=1, le=100, description="Số ảnh mỗi trang"),
        cursor: str | None = Query(None, description="`next_cursor` của trang trước"),
    ) -> None:
        self.angle = angle
        self.limit = limit
        self.cursor = cursor


# Ví dụ Swagger theo seed demo: ảnh tuần 6 (70.0 kg, 18.4 %) và ảnh tuần 0 (72.4 kg, 20.0 %).
_PHOTO_EXAMPLE: dict[str, Any] = {
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
_BEFORE_PHOTO_EXAMPLE: dict[str, Any] = _PHOTO_EXAMPLE | {
    "id": "7a2d3c0f-4e5b-4a6c-9d8e-0f1a2b3c4d5e",
    "taken_at": "2026-10-15T01:00:00Z",
    "taken_date": "2026-10-15",
    "note": None,
    "original_media_id": "4fbc0e96-5d7a-41c2-9e6f-7a8b9cadbecf",
    "watermarked_media_id": "5acd1fa7-6e8b-42d3-8f7a-8b9cadbecfd0",
    "thumbnail_media_id": "6bde20b8-7f9c-43e4-9a8b-9cadbecfd0e1",
    "measurement_id": "7cef31c9-8a0d-44f5-8b9c-adbecfd0e1f2",
    "measured_at": "2026-10-14T23:30:00Z",
    "weight_kg": 72.4,
    "body_fat_pct": 20.0,
    "created_at": "2026-10-15T01:00:05Z",
}


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
        json_schema_extra={"example": _PHOTO_EXAMPLE},
    )

    @field_validator("taken_at", "measured_at", "created_at")
    @classmethod
    def _as_utc(cls, value: datetime | None) -> datetime | None:
        # Driver trả theo múi giờ của phiên DB; contract yêu cầu UTC hậu tố `Z` (Claude_api_respone §2).
        return value.astimezone(timezone.utc) if value is not None else None


class CreatePhotoComparisonRequest(BaseModel):
    """Body của `POST /photo-comparisons`: cặp ảnh Before/After của chính user."""

    before_photo_id: uuid.UUID = Field(..., description="Ảnh chụp trước (Before)")
    after_photo_id: uuid.UUID = Field(..., description="Ảnh chụp sau (After), chụp muộn hơn ảnh Before")
    title: str | None = Field(None, max_length=TITLE_MAX_LENGTH, description="Tiêu đề, ≤ 100 ký tự")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "before_photo_id": "7a2d3c0f-4e5b-4a6c-9d8e-0f1a2b3c4d5e",
                "after_photo_id": "6f1c2b9e-3d4a-4f5b-8c7d-9e0a1b2c3d4e",
                "title": "6 tuần giảm mỡ",
            }
        }
    )

    @field_validator("title")
    @classmethod
    def _blank_title_to_none(cls, value: str | None) -> str | None:
        # Tiêu đề chỉ toàn khoảng trắng không mang thông tin → lưu null thay vì chuỗi rỗng.
        return (value.strip() or None) if value is not None else None


class ListPhotoComparisonsQuery:
    """Query của `GET /photo-comparisons` (gom lại để service ≤ 4 tham số, coding-standards §1)."""

    def __init__(
        self,
        limit: int = Query(20, ge=1, le=100, description="Số cặp mỗi trang"),
        cursor: str | None = Query(None, description="`next_cursor` của trang trước"),
    ) -> None:
        self.limit = limit
        self.cursor = cursor


class PhotoComparisonResponse(BaseModel):
    """Một cặp Before/After đã lưu, nhúng đủ thông số hai ảnh để giao diện dựng thanh trượt so sánh."""

    id: uuid.UUID
    title: str | None
    before: ProgressPhotoResponse
    after: ProgressPhotoResponse
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "8d0f42da-9b1e-45a6-8cad-becfd0e1f203",
                "title": "6 tuần giảm mỡ",
                "before": _BEFORE_PHOTO_EXAMPLE,
                "after": _PHOTO_EXAMPLE,
                "created_at": "2026-11-26T01:05:00Z",
            }
        },
    )

    @field_validator("created_at")
    @classmethod
    def _as_utc(cls, value: datetime) -> datetime:
        # Driver trả theo múi giờ của phiên DB; contract yêu cầu UTC hậu tố `Z` (Claude_api_respone §2).
        return value.astimezone(timezone.utc)
