"""`POST /recovery/predict` (06-ai-contracts.md §2.3): API nội bộ, không tiền tố `/api/v1`, không xác thực (06 §2)."""

from fastapi import APIRouter

from app.contracts import RecoveryPredictionOutput
from app.recovery.heuristic import predict_recovery, register_recovery_model
from app.recovery.schemas import RecoveryPredictRequest

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
    return predict_recovery(request)
