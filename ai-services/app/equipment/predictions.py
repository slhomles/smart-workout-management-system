"""Hậu xử lý xác suất thô của model thành danh sách `AiPrediction` (spec ai-equipment-classify §6 ý 7).

Hàm thuần, không I/O. Kết quả luôn thuộc 27 nhãn của 06-ai-contracts.md §2.5, không trùng nhãn,
`confidence` giảm dần trong (0, 1], hoà điểm thì sắp theo `label` tăng dần để đầu ra tất định.
"""

import math
from collections.abc import Mapping

from app.contracts import AiPrediction
from app.equipment.labels import normalize_class_name

# Backend chỉ lưu top-5 (`MAX_STORED_PREDICTIONS`) dù 06 §2.4 cho tối đa 20; nhãn fine-tune ánh xạ 1-1
# nên cắt ở 5 không mất thông tin backend dùng tới.
TOP_K = 5
# Backend lưu `confidence` kiểu numeric(5,4).
CONFIDENCE_DECIMALS = 4


def build_predictions(probabilities: Mapping[str, float], label_map: Mapping[str, str],
                      top_k: int = TOP_K) -> list[AiPrediction]:
    """Ánh xạ xác suất theo tên lớp sang `ai_label`, làm sạch, gộp, làm tròn rồi lấy `top_k` nhãn cao nhất."""
    best_by_label = _best_confidence_by_label(probabilities, label_map)
    ranked = _rank_rounded(best_by_label)
    return [AiPrediction(label=label, confidence=confidence) for label, confidence in ranked[:top_k]]


def _best_confidence_by_label(probabilities: Mapping[str, float], label_map: Mapping[str, str]) -> dict[str, float]:
    best_by_label: dict[str, float] = {}
    for class_name, probability in probabilities.items():
        label = label_map.get(normalize_class_name(class_name))
        # NaN/vô cực là đầu ra hỏng của model, không có nghĩa xác suất nên bỏ hẳn thay vì kẹp về 0 hoặc 1.
        if label is None or not math.isfinite(probability):
            continue
        # Sai số dấu phẩy động có thể đẩy xác suất ra ngoài [0, 1], mà hợp đồng chỉ nhận [0, 1].
        confidence = min(max(probability, 0.0), 1.0)
        # Nhiều tên lớp có thể ra cùng một nhãn sau chuẩn hoá; giữ mức tin cậy cao nhất để nhãn không bị trùng.
        best_by_label[label] = max(confidence, best_by_label.get(label, 0.0))
    return best_by_label


def _rank_rounded(confidence_by_label: Mapping[str, float]) -> list[tuple[str, float]]:
    rounded = {label: round(confidence, CONFIDENCE_DECIMALS) for label, confidence in confidence_by_label.items()}
    # Nhãn làm tròn về 0 không mang thông tin và backend không cần lưu.
    positive = [(label, confidence) for label, confidence in rounded.items() if confidence > 0]
    return sorted(positive, key=lambda item: (-item[1], item[0]))
