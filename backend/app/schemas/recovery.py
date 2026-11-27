"""Schema Pydantic cho /recovery (chức năng 2: Heatmap phục hồi, lịch sử dự đoán phục hồi).

Heatmap lấy nguyên cột của view training.v_muscle_recovery_status (02_training.sql); lịch sử dự đoán
lấy từ training.recovery_predictions (06_training.sql) kèm buổi tập và nhóm cơ.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import JsonDict

# View trả `text` chứ không phải enum DB, nên kiểu nằm ở đây thay vì models/enums.py (spec §6 ý 7).
RecoveryStatus = Literal["fatigued", "recovering", "ready"]

# Ví dụ theo seed: nhóm cơ `chest` ("Ngực") của demo sau một buổi đẩy ngực.
_EXAMPLE_MUSCLE_RECOVERY: JsonDict = {
    "muscle_group_id": 1,
    "muscle_code": "chest",
    "muscle_name": "Ngực",
    "heatmap_region_key": "chest",
    "recovery_status": "fatigued",
    "recovery_pct": 2,
    "remaining_hours": 59.0,
    "fatigue_score": 80.0,
    "last_trained_at": "2026-11-27T01:00:00Z",
    "recovered_at": "2026-11-29T13:00:00Z",
    "last_session_id": "7c1e9a52-3b8d-4f60-a2e4-9d5b1c7f3a10",
    "model_version": "recovery-v1",
}
_EXAMPLE_PREDICTION: JsonDict = {
    "session_id": "7c1e9a52-3b8d-4f60-a2e4-9d5b1c7f3a10",
    "session_name": "Push – Ngực/Vai/Tay sau",
    "trained_at": "2026-11-27T01:00:00Z",
    "muscle_group_id": 1,
    "muscle_code": "chest",
    "muscle_name": "Ngực",
    "model_version": "recovery-v1",
    "fatigue_score": 80.0,
    "recovered_at": "2026-11-29T13:00:00Z",
    "predicted_at": "2026-11-27T01:00:05Z",
}


class MuscleRecoveryListQuery(BaseModel):
    """Query của `GET /recovery/muscle-groups`, gom vào một model (coding-standards §1)."""

    recovery_status: RecoveryStatus | None = Field(None, description="Lọc theo trạng thái phục hồi")
    limit: int = Field(20, ge=1, le=100)
    cursor: str | None = Field(None, description="`next_cursor` của trang trước")


class RecoveryPredictionListQuery(BaseModel):
    """Query của `GET /recovery/predictions`; `muscle_group_id` là smallint của catalog.muscle_groups."""

    muscle_group_id: int | None = Field(None, ge=1, le=32767, description="Chỉ lấy dự đoán của nhóm cơ này")
    limit: int = Field(20, ge=1, le=100)
    cursor: str | None = Field(None, description="`next_cursor` của trang trước")


class MuscleRecoveryStatusResponse(BaseModel):
    """Trạng thái phục hồi hiện tại của một nhóm cơ trên Heatmap (giá trị lấy nguyên từ view)."""

    muscle_group_id: int
    muscle_code: str
    muscle_name: str
    heatmap_region_key: str
    recovery_status: RecoveryStatus = Field(
        ..., description="fatigued (đỏ, < 50%) | recovering (vàng, 50–99%) | ready (xanh, đã hồi phục)"
    )
    recovery_pct: int = Field(..., description="Phần trăm đã hồi phục (0–100)")
    remaining_hours: float = Field(..., description="Số giờ còn lại tới khi hồi phục hoàn toàn (0 nếu đã hồi phục)")
    fatigue_score: float | None = Field(..., description="Mức mệt mỏi ngay sau buổi tập gần nhất (0–100)")
    last_trained_at: datetime | None = Field(..., description="Lúc kết thúc buổi tập gần nhất có dự đoán")
    recovered_at: datetime | None = Field(..., description="Thời điểm dự kiến hồi phục hoàn toàn")
    last_session_id: uuid.UUID | None = Field(..., description="Buổi tập của dự đoán đang dùng")
    model_version: str | None

    # `model_version` là tên cột DB (KEYS-MRS), trùng tiền tố `model_` mà Pydantic dành riêng.
    model_config = ConfigDict(
        from_attributes=True, protected_namespaces=(), json_schema_extra={"example": _EXAMPLE_MUSCLE_RECOVERY}
    )


class RecoveryPredictionResponse(BaseModel):
    """Bản dự đoán mới nhất của một cặp (buổi tập, nhóm cơ)."""

    session_id: uuid.UUID
    session_name: str | None
    trained_at: datetime = Field(..., description="Lúc kết thúc buổi tập (hoặc lúc bắt đầu nếu chưa kết thúc)")
    muscle_group_id: int
    muscle_code: str
    muscle_name: str
    model_version: str
    fatigue_score: float = Field(..., description="Mức mệt mỏi ngay sau buổi tập (0–100)")
    recovered_at: datetime = Field(..., description="Thời điểm dự kiến hồi phục hoàn toàn")
    predicted_at: datetime = Field(..., description="Lúc chạy dự đoán")

    model_config = ConfigDict(
        from_attributes=True, protected_namespaces=(), json_schema_extra={"example": _EXAMPLE_PREDICTION}
    )
