"""Client gọi AI service nhận diện thiết bị phòng tập (spec equipment-recognition §6 ý 4).

Hợp đồng tạm phía backend, chờ AI team xác nhận (Q2): `POST {AI_SERVICE_URL}/equipment-recognition/classify`,
multipart part `image`. Mọi lỗi (không gọi được, status ≠ 200, JSON hỏng, sai schema) đều thành 503
`service_unavailable` với cùng một message; chi tiết chỉ ghi log server (Claude_api_respone.md §3).
"""

import logging

import httpx
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.exceptions import ServiceUnavailableError
from app.schemas.equipment_scan import AiClassifyResult

logger = logging.getLogger("app.equipment_recognition")

# Hằng số module thay vì biến cấu hình: thêm biến phải sửa core/config.py (file core, spec §6 ý 4, Q8).
_TIMEOUT_SECONDS = 10.0
_CLASSIFY_PATH = "/equipment-recognition/classify"
UNAVAILABLE_MESSAGE = "Dịch vụ nhận diện thiết bị tạm thời không khả dụng"


async def classify_image(data: bytes, filename: str | None, content_type: str) -> AiClassifyResult:
    """Gửi nguyên bytes ảnh (giữ tên file, content type) sang AI service, trả kết quả đã kiểm schema.

    Ném `ServiceUnavailableError` (503) cho mọi lỗi của AI service.
    """
    url = f"{get_settings().AI_SERVICE_URL.rstrip('/')}{_CLASSIFY_PATH}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(url, files={"image": (filename, data, content_type)})
    except httpx.HTTPError as exc:
        logger.warning("equipment recognition ai unreachable: %s", type(exc).__name__)
        raise ServiceUnavailableError(UNAVAILABLE_MESSAGE) from exc
    if response.status_code != 200:
        logger.warning("equipment recognition ai returned HTTP %s", response.status_code)
        raise ServiceUnavailableError(UNAVAILABLE_MESSAGE)
    try:
        return AiClassifyResult.model_validate_json(response.content)
    except ValidationError as exc:
        logger.warning("equipment recognition ai response violates contract: %s error(s)", exc.error_count())
        raise ServiceUnavailableError(UNAVAILABLE_MESSAGE) from exc
