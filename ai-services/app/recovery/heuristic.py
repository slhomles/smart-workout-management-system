"""Thuật toán tất định `heuristic-v1` dự đoán phục hồi cơ (spec ai-recovery-predict §6 ý 5).

Hàm thuần: cùng đầu vào luôn cho cùng đầu ra, không đọc giờ hiện tại, không ngẫu nhiên, không giữ trạng thái
(06-ai-contracts.md §2.3). Đổi công thức hay hằng số thì PHẢI đổi `MODEL_VERSION`, vì phiên bản nằm trong
khoá chính của `training.recovery_predictions`.
"""

from datetime import datetime, timedelta, timezone

from app.contracts import PredictedRecovery, RecoveryPredictionOutput
from app.core.models import registry
from app.recovery.schemas import MuscleLoadRequest, RecoveryPredictRequest

MODEL_KEY = "recovery"
MODEL_VERSION = "heuristic-v1"

# Buổi không ghi RPE thì giả định mức gắng sức vừa phải.
DEFAULT_RPE = 7.0
# RPE 8 ≈ còn khoảng 2 rep (RIR ≈ 10 − RPE, COMMENT `training.exercise_sets.rpe`): mốc của một hiệp hiệu quả;
# mức mệt tăng tỷ lệ thuận với RPE quanh mốc này.
REFERENCE_RPE = 8.0
# Khoảng 10 hiệp hiệu quả cho một nhóm cơ trong một buổi thì đạt mệt tối đa: AGENT_RESOURCES.md §2 ghi phì đại
# cần ~10 set/nhóm cơ/tuần, nên dồn cả tuần vào một buổi là mức tải cao nhất.
POINTS_PER_EFFECTIVE_SET = 10.0
# Volume tuyệt đối phụ thuộc sức mạnh từng người nên chỉ cộng thêm và bị chặn trần; vẫn đưa vào vì
# "Mô tả dự án" bước 2–3 yêu cầu tính theo khối lượng vận động.
VOLUME_KG_PER_POINT = 200.0
MAX_VOLUME_POINTS = 20.0
# Thang điểm mệt 0–100 theo CHECK `ck_recovery_predictions_fatigue`; 1 chữ số thập phân vừa `numeric(5,2)`.
MAX_FATIGUE_SCORE = 100.0
FATIGUE_SCORE_DECIMALS = 1
# Mệt 50 cho đúng `base_recovery_hours` (thời gian phục hồi tham chiếu, COMMENT
# `catalog.muscle_groups.base_recovery_hours`); khoảng phục hồi trải từ 0,5 đến 1,5 lần mốc này.
MIN_RECOVERY_FACTOR = 0.5
SECONDS_PER_HOUR = 3600


def predict_recovery(request: RecoveryPredictRequest) -> RecoveryPredictionOutput:
    """Tính mức mệt và thời điểm hồi phục cho từng nhóm cơ, giữ đúng thứ tự `muscle_loads`."""
    predictions = [_predict_muscle_recovery(load, request.trained_at) for load in request.muscle_loads]
    return RecoveryPredictionOutput(model_version=MODEL_VERSION, predictions=predictions)


def register_recovery_model() -> None:
    """Đăng ký model `recovery` cho `/health`; heuristic không phải nạp gì nên sẵn sàng ngay. Gọi lại không đổi gì."""
    registry.register(MODEL_KEY)
    registry.mark_ready(MODEL_KEY, MODEL_VERSION)


def _predict_muscle_recovery(load: MuscleLoadRequest, trained_at: datetime) -> PredictedRecovery:
    fatigue_score = _fatigue_score(load)
    recovered_at = _recovered_at(trained_at, load.base_recovery_hours, fatigue_score)
    return PredictedRecovery(muscle_group_id=load.muscle_group_id, fatigue_score=fatigue_score,
                             recovered_at=recovered_at)


def _fatigue_score(load: MuscleLoadRequest) -> float:
    rpe = load.avg_rpe if load.avg_rpe is not None else DEFAULT_RPE
    set_points = POINTS_PER_EFFECTIVE_SET * load.effective_sets * rpe / REFERENCE_RPE
    volume_points = min(load.weighted_volume_kg / VOLUME_KG_PER_POINT, MAX_VOLUME_POINTS)
    return round(min(set_points + volume_points, MAX_FATIGUE_SCORE), FATIGUE_SCORE_DECIMALS)


def _recovered_at(trained_at: datetime, base_recovery_hours: int, fatigue_score: float) -> datetime:
    # Dùng điểm đã làm tròn để thời điểm hồi phục khớp đúng điểm trả về; khi đó phần lẻ của số giây luôn là
    # bội của 0,2 nên làm tròn tới giây không bao giờ rơi vào ca .5 (spec §6 ý 5).
    recovery_hours = base_recovery_hours * (MIN_RECOVERY_FACTOR + fatigue_score / MAX_FATIGUE_SCORE)
    return trained_at.astimezone(timezone.utc) + timedelta(seconds=round(recovery_hours * SECONDS_PER_HOUR))
