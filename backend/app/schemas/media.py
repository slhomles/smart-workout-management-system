"""Schema Pydantic cho phát media: /media (metadata + URL tạm của ảnh, GIF, video)."""

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

# Ví dụ Swagger theo seed `gif-row` (catalog/exercises/dumbbell-row/demo.gif, 91_test_catalog.sql) ở chế độ
# STORAGE_BACKEND=local. `size_bytes`, `duration_ms`, `width_px`, `height_px` lấy theo bản ghi seed `gif-row`
# trong DB; `id` và `created_at` chỉ minh hoạ vì seed sinh `id` ngẫu nhiên và `created_at` tương đối.
_GIF_ROW_EXAMPLE: dict[str, Any] = {
    "id": "9b2e4c1a-6d3f-4e8b-a5c7-1f0d2e3b4a59",
    "mime_type": "image/gif",
    "size_bytes": 679190,
    "width_px": 480,
    "height_px": 360,
    "duration_ms": 4310,
    "url": "/api/v1/media/9b2e4c1a-6d3f-4e8b-a5c7-1f0d2e3b4a59/content",
    "url_expires_at": None,
    "created_at": "2026-05-12T03:00:00Z",
}


class MediaResponse(BaseModel):
    """Metadata của một file media kèm URL tạm để tải; không lộ bucket, key hay người tải lên."""

    id: uuid.UUID
    mime_type: str
    size_bytes: int | None
    width_px: int | None
    height_px: int | None
    duration_ms: int | None
    url: str
    url_expires_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"example": _GIF_ROW_EXAMPLE},
    )

    @field_validator("url_expires_at", "created_at")
    @classmethod
    def _as_utc(cls, value: datetime | None) -> datetime | None:
        # Driver trả theo múi giờ của phiên DB; contract yêu cầu UTC hậu tố `Z` (Claude_api_respone §2).
        return value.astimezone(timezone.utc) if value is not None else None
