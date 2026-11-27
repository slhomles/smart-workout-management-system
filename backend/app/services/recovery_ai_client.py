"""Client gọi AI service dự đoán phục hồi cơ (spec workout-routine §6 ý 10).

Hợp đồng tạm phía backend, chờ AI team xác nhận (Q5): `POST {AI_SERVICE_URL}/recovery/predict`.
Mọi lỗi được quy về `RecoveryServiceError` với `reason` ổn định để service dịch sang 503.
"""

import logging
from typing import Literal

import httpx
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.recovery import RecoveryPredictionInput, RecoveryPredictionOutput

logger = logging.getLogger("app.recovery_ai")

# Hằng số module thay vì biến cấu hình: thêm biến phải sửa core/config.py (file core, spec §6 ý 10).
_TIMEOUT_SECONDS = 10.0
_PREDICT_PATH = "/recovery/predict"

RecoveryErrorReason = Literal["down", "invalid_response"]


class RecoveryServiceError(Exception):
    """AI service không gọi được (`down`) hoặc trả dữ liệu sai hợp đồng (`invalid_response`)."""

    def __init__(self, reason: RecoveryErrorReason) -> None:
        super().__init__(reason)
        self.reason: RecoveryErrorReason = reason


async def predict_recovery(
    payload: RecoveryPredictionInput, *, transport: httpx.AsyncBaseTransport | None = None
) -> RecoveryPredictionOutput:
    """Gửi tải theo nhóm cơ của một buổi tập, trả dự đoán đã kiểm tra theo schema.

    `transport` chỉ dùng trong test (`httpx.MockTransport`) để không gọi mạng thật.
    """
    url = f"{get_settings().AI_SERVICE_URL.rstrip('/')}{_PREDICT_PATH}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, transport=transport) as client:
            response = await client.post(url, json=payload.model_dump(mode="json"))
    except httpx.HTTPError as exc:
        logger.warning("recovery ai unreachable: %s", type(exc).__name__)
        raise RecoveryServiceError("down") from exc
    if not response.is_success:
        logger.warning("recovery ai returned HTTP %s", response.status_code)
        raise RecoveryServiceError("down")
    try:
        return RecoveryPredictionOutput.model_validate_json(response.content)
    except ValidationError as exc:
        logger.warning("recovery ai response violates contract: %s error(s)", exc.error_count())
        raise RecoveryServiceError("invalid_response") from exc
