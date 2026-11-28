"""Phân loại thiết bị trên một ảnh: giải mã, nạp model, suy luận, hậu xử lý (spec ai-equipment-classify §6 ý 8)."""

import threading
from time import perf_counter

from app.contracts import AiClassifyResult
from app.equipment.image_io import decode_image
from app.equipment.loader import get_equipment_model
from app.equipment.predictions import build_predictions

# Ultralytics khuyến cáo không dùng chung một instance model giữa nhiều thread, nên suy luận chạy tuần tự.
_inference_lock = threading.Lock()


def classify_image(data: bytes) -> AiClassifyResult:
    """Trả tối đa 5 nhãn thiết bị cho ảnh; ảnh sai → 400, model không nạp được → 503."""
    # Kiểm ảnh trước khi nạp model để ảnh hỏng không kích hoạt việc nạp model nặng.
    image = decode_image(data)
    model = get_equipment_model()
    with _inference_lock:
        # Đo trong khoá: `latency_ms` chỉ là thời gian suy luận, không tính giải mã, nạp model hay chờ khoá.
        started_at = perf_counter()
        probabilities = model.classifier.predict_proba(image)
        latency_ms = round((perf_counter() - started_at) * 1000)
    return AiClassifyResult(
        model_name=model.model_name,
        model_version=model.model_version,
        latency_ms=latency_ms,
        predictions=build_predictions(probabilities, model.label_map),
    )
