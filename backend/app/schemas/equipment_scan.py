"""Schema Pydantic cho /ai/equipment-scans (chức năng 7: nhận diện thiết bị)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ScanFeedback


class EquipmentScanSummaryResponse(BaseModel):
    """Một lần quét kèm kết quả top-1 (đọc từ view ai.v_equipment_scan_results)."""

    model_config = ConfigDict(
        from_attributes=True,
        # `model_name`/`model_version` là tên cột DB (tên model AI), không phải thuộc tính Pydantic.
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "id": "0b7f3c2e-5d1a-4c3b-9e8f-1a2b3c4d5e6f",
                "model_name": "yolov8_cls_gym",
                "model_version": "1.0.0",
                "latency_ms": 180,
                "scanned_at": "2026-11-26T03:20:41Z",
                "predicted_equipment_id": 12,
                "predicted_equipment_code": "cable_crossover",
                "predicted_equipment_name": "Máy kéo cáp đôi",
                "confidence": 0.9234,
                "is_confident": True,
                "feedback": None,
                "corrected_equipment_id": None,
                "resolved_equipment_id": 12,
            }
        },
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
