"""Schema Pydantic cho /ai/equipment-scans (chức năng 7: nhận diện thiết bị)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ScanFeedback

# Giới hạn cột `integer` của Postgres (ai.equipment_scans.latency_ms).
_INT4_MAX = 2_147_483_647

# Ví dụ theo seed: thiết bị `cable_crossover` (id 15) có nhãn AI `cable_crossover_machine`.
_SCAN_SUMMARY_EXAMPLE: dict[str, Any] = {
    "id": "0b7f3c2e-5d1a-4c3b-9e8f-1a2b3c4d5e6f",
    "model_name": "yolov8_cls_gym",
    "model_version": "1.0.0",
    "latency_ms": 180,
    "scanned_at": "2026-11-26T03:20:41Z",
    "predicted_equipment_id": 15,
    "predicted_equipment_code": "cable_crossover",
    "predicted_equipment_name": "Máy kéo cáp đôi",
    "confidence": 0.9234,
    "is_confident": True,
    "feedback": None,
    "corrected_equipment_id": None,
    "resolved_equipment_id": 15,
}


class EquipmentScanSummaryResponse(BaseModel):
    """Một lần quét kèm kết quả top-1 (đọc từ view ai.v_equipment_scan_results)."""

    model_config = ConfigDict(
        from_attributes=True,
        # `model_name`/`model_version` là tên cột DB (tên model AI), không phải thuộc tính Pydantic.
        protected_namespaces=(),
        json_schema_extra={"example": _SCAN_SUMMARY_EXAMPLE},
    )

    id: uuid.UUID
    model_name: str
    model_version: str
    latency_ms: int | None
    scanned_at: datetime
    predicted_equipment_id: int | None
    predicted_equipment_code: str | None
    predicted_equipment_name: str | None
    confidence: float | None
    is_confident: bool
    feedback: ScanFeedback | None
    corrected_equipment_id: int | None
    resolved_equipment_id: int | None


class EquipmentPredictionSchema(BaseModel):
    """Một thiết bị model dự đoán cho lần quét; `confidence` là giá trị đã lưu (numeric(5,4))."""

    model_config = ConfigDict(from_attributes=True)

    equipment_id: int
    equipment_code: str
    equipment_name: str
    confidence: float = Field(..., ge=0, le=1)


class SuggestedExerciseSchema(BaseModel):
    """Bài tập gợi ý dùng thiết bị top-1 (lấy qua service của Catalog)."""

    model_config = ConfigDict(from_attributes=True)

    exercise_id: int
    slug: str
    exercise_name: str
    difficulty_rank: int


class EquipmentScanResponse(EquipmentScanSummaryResponse):
    """Kết quả một lần quét vừa tạo: top-1, tối đa 5 dự đoán và bài tập gợi ý (rỗng nếu chưa đủ tin cậy)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                **_SCAN_SUMMARY_EXAMPLE,
                "predictions": [
                    {
                        "equipment_id": 15,
                        "equipment_code": "cable_crossover",
                        "equipment_name": "Máy kéo cáp đôi",
                        "confidence": 0.9234,
                    },
                    {
                        "equipment_id": 14,
                        "equipment_code": "lat_pulldown_machine",
                        "equipment_name": "Máy kéo xô",
                        "confidence": 0.0512,
                    },
                ],
                "suggested_exercises": [
                    {"exercise_id": 12, "slug": "cable-chest-fly", "exercise_name": "Ép ngực với cáp", "difficulty_rank": 1},
                    {"exercise_id": 5, "slug": "face-pull", "exercise_name": "Face Pull", "difficulty_rank": 1},
                ],
            }
        },
    )

    predictions: list[EquipmentPredictionSchema]
    suggested_exercises: list[SuggestedExerciseSchema]


# --- Hợp đồng nội bộ với AI service (spec §6 ý 4), không xuất hiện trong API ---
class AiPrediction(BaseModel):
    """Một nhãn lớp YOLOv8 kèm độ tin cậy do AI service trả về."""

    label: str = Field(..., min_length=1, max_length=100)
    confidence: float = Field(..., ge=0, le=1)


class AiClassifyResult(BaseModel):
    """Response 200 của `POST /equipment-recognition/classify`; sai schema thì coi như AI service lỗi."""

    # `model_name`/`model_version` là field của hợp đồng AI, không phải thuộc tính Pydantic.
    model_config = ConfigDict(protected_namespaces=())

    model_name: str = Field(..., min_length=1, max_length=50)
    model_version: str = Field(..., min_length=1, max_length=50)
    latency_ms: int | None = Field(None, ge=0, le=_INT4_MAX)
    predictions: list[AiPrediction] = Field(..., max_length=20)
