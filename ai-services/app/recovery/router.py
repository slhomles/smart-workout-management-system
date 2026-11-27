"""`POST /recovery/predict` (06-ai-contracts.md §2.3): API nội bộ, không tiền tố `/api/v1`, không xác thực (06 §2)."""

import logging

from fastapi import APIRouter

from app.contracts import RecoveryPredictionOutput
from app.recovery.heuristic import predict_recovery, register_recovery_model
from app.recovery.schemas import RecoveryPredictRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Recovery"])

# Đăng ký lúc import thay vì startup hook (spec ai-recovery-predict §6 ý 7): `main.py` là file core nên không thêm
# hook ở đó; `on_startup`/`lifespan` của router lại chạy sau fixture `clean_registry`, làm test `/health` kỳ vọng
# `models == {}` trượt. Import thì `uvicorn app.main:app` có `recovery` ngay, còn test vẫn bắt đầu với registry trống.
register_recovery_model()


@router.post(
    "/recovery/predict",
    response_model=RecoveryPredictionOutput,
    status_code=200,
    summary="Dự đoán phục hồi cơ theo tải tập của một buổi",
    description=(
        "Tính `heuristic-v1` tất định cho từng phần tử `muscle_loads`, trả `predictions` giữ đúng thứ tự gửi lên "
        "(`muscle_loads` rỗng thì `predictions: []`). API nội bộ, không xác thực (06-ai-contracts §2)."
    ),
    responses={
        422: {"description": "validation_error: dữ liệu gửi lên không hợp lệ (format lỗi Claude_api_respone §3)"},
    },
)
async def predict(request: RecoveryPredictRequest) -> RecoveryPredictionOutput:
    """Trả mức mệt và thời điểm hồi phục của từng nhóm cơ trong buổi tập."""
    result = predict_recovery(request)
    # Chỉ ghi số phần tử và phiên bản model: `user_id`, `session_id`, `trained_at` hay payload là dữ liệu người dùng,
    # không được vào log (spec ai-recovery-predict §6 ý 9; 06-ai-contracts §5).
    logger.debug("recovery predicted for %d muscle groups with %s", len(request.muscle_loads), result.model_version)
    return result
