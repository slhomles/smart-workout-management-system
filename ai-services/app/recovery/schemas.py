"""Schema đầu vào của dự đoán phục hồi cơ (06-ai-contracts.md §2.3; spec ai-recovery-predict §6 ý 4).

Tên field, kiểu và tính bắt buộc giống hệt `MuscleLoad` / `RecoveryPredictionInput` trong `app.contracts`.
Model viết độc lập thay vì kế thừa, vì ghi đè `list[MuscleLoad]` bằng list kiểu con làm mypy báo lỗi.
"""

import uuid

from pydantic import AwareDatetime, BaseModel


class MuscleLoadRequest(BaseModel):
    """Tải tập của một nhóm cơ trong buổi: một dòng `training.v_session_muscle_load` kèm `base_recovery_hours`."""

    muscle_group_id: int
    direct_sets: int
    effective_sets: float
    total_reps: int
    weighted_volume_kg: float
    # Key bắt buộc nhưng giá trị được phép null (buổi không ghi RPE), giống `MuscleLoad.avg_rpe`.
    avg_rpe: float | None
    base_recovery_hours: int


class RecoveryPredictRequest(BaseModel):
    """Body yêu cầu dự đoán phục hồi: tải tập theo nhóm cơ của một buổi tập."""

    session_id: uuid.UUID
    user_id: uuid.UUID
    trained_at: AwareDatetime
    muscle_loads: list[MuscleLoadRequest]
