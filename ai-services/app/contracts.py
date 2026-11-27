"""Model Pydantic của hợp đồng backend ↔ AI service (docs/architecture/06-ai-contracts.md §2).

Tên field, kiểu và giới hạn PHẢI khớp schema phía backend:
`backend/app/schemas/recovery.py` (RecoveryPredictionInput/Output) và
`backend/app/schemas/equipment_scan.py` (AiClassifyResult). Đổi ở đây thì sửa tài liệu trước.
"""

import uuid
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

MAX_PREDICTIONS = 20
_INT4_MAX = 2_147_483_647

# Nhãn lớp model nhận diện thiết bị = catalog.equipment_aliases(alias_type='ai_label') (06-ai-contracts.md §2.5).
EQUIPMENT_LABELS: tuple[str, ...] = (
    "barbell", "ez_curl_bar", "dumbbell", "kettlebell", "flat_bench", "adjustable_bench", "power_rack",
    "smith_machine", "cable_crossover_machine", "lat_pulldown_machine", "seated_cable_row_machine",
    "leg_press_machine", "leg_extension_machine", "leg_curl_machine", "chest_press_machine", "pec_deck_machine",
    "shoulder_press_machine", "pull_up_bar", "dip_station", "treadmill", "stationary_bike", "rowing_machine",
    "resistance_band", "jump_rope", "plyo_box", "medicine_ball", "ab_wheel",
)


class MuscleLoad(BaseModel):
    muscle_group_id: int
    direct_sets: int
    effective_sets: float
    total_reps: int
    weighted_volume_kg: float
    avg_rpe: float | None
    base_recovery_hours: int


class RecoveryPredictionInput(BaseModel):
    session_id: uuid.UUID
    user_id: uuid.UUID
    trained_at: AwareDatetime
    muscle_loads: list[MuscleLoad]


class PredictedRecovery(BaseModel):
    muscle_group_id: int
    fatigue_score: float = Field(..., ge=0, le=100)
    recovered_at: AwareDatetime


class RecoveryPredictionOutput(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_version: str = Field(..., min_length=1, max_length=50)
    predictions: list[PredictedRecovery]


class AiPrediction(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    confidence: float = Field(..., ge=0, le=1)


class AiClassifyResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_name: str = Field(..., min_length=1, max_length=50)
    model_version: str = Field(..., min_length=1, max_length=50)
    latency_ms: int | None = Field(None, ge=0, le=_INT4_MAX)
    predictions: list[AiPrediction] = Field(..., max_length=MAX_PREDICTIONS)


class HealthResponse(BaseModel):
    status: str
    models: dict[str, str | None]
    checked_at: datetime
