"""Schema đầu vào của dự đoán phục hồi cơ (06-ai-contracts.md §2.3; spec ai-recovery-predict §6 ý 4).

Tên field, kiểu và tính bắt buộc giống hệt `MuscleLoad` / `RecoveryPredictionInput` trong `app.contracts`.
Model viết độc lập thay vì kế thừa, vì ghi đè `list[MuscleLoad]` bằng list kiểu con làm mypy báo lỗi.
Giới hạn giá trị lấy theo CHECK của DB nên mọi tải backend gửi được đều hợp lệ; dữ liệu sai bị Pydantic từ chối
thành `422 validation_error` (handler core) thay vì cho kết quả sai hoặc `500`.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

# `catalog.muscle_groups.id` là smallint sinh bằng IDENTITY nên chỉ nhận 1–32767.
MIN_MUSCLE_GROUP_ID = 1
MAX_MUSCLE_GROUP_ID = 32767
# CHECK `ck_exercise_sets_rpe`: rpe NULL hoặc trong 1–10.
MIN_RPE = 1.0
MAX_RPE = 10.0
# CHECK `ck_muscle_groups_recovery_hours`: base_recovery_hours trong 12–168 giờ.
MIN_BASE_RECOVERY_HOURS = 12
MAX_BASE_RECOVERY_HOURS = 168
# Thời gian phục hồi dài nhất heuristic-v1 có thể trả = MAX_BASE_RECOVERY_HOURS × 1,5 (hệ số tối đa, spec §6 ý 5).
# Viết số cứng thay vì import từ `heuristic.py` vì heuristic đã import module này (tránh vòng import).
MAX_RECOVERY_HOURS = 252

NonNegativeFiniteFloat = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Rpe = Annotated[float, Field(ge=MIN_RPE, le=MAX_RPE, allow_inf_nan=False)]

# Đúng request ví dụ của 06-ai-contracts.md §2.3; UUID là dữ liệu giả lập.
REQUEST_EXAMPLE: dict[str, Any] = {
    "session_id": "7c1e9a52-3b8d-4f60-a2e4-9d5b1c7f3a10",
    "user_id": "00000000-0000-0000-0000-000000000003",
    "trained_at": "2026-11-27T01:00:00Z",
    "muscle_loads": [
        {"muscle_group_id": 1, "direct_sets": 4, "effective_sets": 5.5, "total_reps": 40,
         "weighted_volume_kg": 2400.0, "avg_rpe": 8.0, "base_recovery_hours": 72},
    ],
}


class MuscleLoadRequest(BaseModel):
    """Tải tập của một nhóm cơ trong buổi: một dòng `training.v_session_muscle_load` kèm `base_recovery_hours`."""

    muscle_group_id: int = Field(..., ge=MIN_MUSCLE_GROUP_ID, le=MAX_MUSCLE_GROUP_ID)
    direct_sets: int = Field(..., ge=0)
    effective_sets: NonNegativeFiniteFloat
    total_reps: int = Field(..., ge=0)
    weighted_volume_kg: NonNegativeFiniteFloat
    # Key bắt buộc nhưng giá trị được phép null (buổi không ghi RPE), giống `MuscleLoad.avg_rpe`.
    # Giới hạn đặt trong `Annotated` để Pydantic dựng schema nullable: lỗi gắn đúng `avg_rpe`, không thêm hậu tố
    # kiểu của union (vd `avg_rpe.float`).
    avg_rpe: Rpe | None
    base_recovery_hours: int = Field(..., ge=MIN_BASE_RECOVERY_HOURS, le=MAX_BASE_RECOVERY_HOURS)


class RecoveryPredictRequest(BaseModel):
    """Body yêu cầu dự đoán phục hồi: tải tập theo nhóm cơ của một buổi tập."""

    model_config = ConfigDict(json_schema_extra={"example": REQUEST_EXAMPLE})

    # Chỉ nhận vào để khớp hợp đồng; heuristic-v1 không dùng khi tính.
    session_id: uuid.UUID
    user_id: uuid.UUID
    trained_at: AwareDatetime
    muscle_loads: list[MuscleLoadRequest]

    @field_validator("trained_at")
    @classmethod
    def _ensure_recovery_time_representable(cls, trained_at: datetime) -> datetime:
        """Từ chối mốc tập mà đổi sang UTC hoặc cộng thời gian phục hồi tối đa vượt khỏi phạm vi `datetime`."""
        try:
            # Chỉ cần biết phép tính có tràn hay không nên bỏ kết quả; heuristic tự tính lại thời điểm thật.
            trained_at.astimezone(timezone.utc) + timedelta(hours=MAX_RECOVERY_HOURS)
        except OverflowError as exc:
            # Đổi thành lỗi validation gắn `trained_at`, nếu không heuristic sẽ ném OverflowError thành `500`.
            raise ValueError("trained_at quá gần giới hạn thời gian, không tính được thời điểm hồi phục") from exc
        return trained_at

    @field_validator("muscle_loads")
    @classmethod
    def _ensure_unique_muscle_groups(cls, muscle_loads: list[MuscleLoadRequest]) -> list[MuscleLoadRequest]:
        """Mỗi nhóm cơ chỉ một phần tử, vì response phải có đúng một dự đoán cho mỗi `muscle_group_id` (06 §2.3)."""
        muscle_group_ids = [load.muscle_group_id for load in muscle_loads]
        if len(set(muscle_group_ids)) != len(muscle_group_ids):
            raise ValueError("muscle_group_id không được trùng trong muscle_loads")
        return muscle_loads
