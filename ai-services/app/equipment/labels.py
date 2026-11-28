"""Bảng ánh xạ tên lớp của model sang `ai_label` (spec ai-equipment-classify §6 ý 6, 7; 06-ai-contracts.md §2.5).

Nhãn đích luôn thuộc `EQUIPMENT_LABELS`; danh sách 27 nhãn chỉ khai báo một lần ở `app.contracts`.
Khoá của mọi bảng ở dạng đã qua `normalize_class_name`.
"""

from collections.abc import Mapping
from types import MappingProxyType

from app.contracts import EQUIPMENT_LABELS

# Bảng dùng chung giữa các request nên bọc chỉ-đọc để không ai sửa nhầm lúc chạy.
# Model fine-tune được huấn luyện đúng trên 27 nhãn của 06 §2.5 nên ánh xạ 1-1.
FINETUNED_LABEL_MAP: Mapping[str, str] = MappingProxyType({label: label for label in EQUIPMENT_LABELS})

# Model dự phòng YOLOv8n-cls (ImageNet) chỉ có 4 lớp tương ứng thiết bị gym; lớp khác bị bỏ (spec §6 ý 6).
IMAGENET_FALLBACK_LABEL_MAP: Mapping[str, str] = MappingProxyType({
    "barbell": "barbell",
    "dumbbell": "dumbbell",
    "horizontal_bar": "pull_up_bar",
    "parallel_bars": "dip_station",
})


def normalize_class_name(name: str) -> str:
    """Đưa tên lớp về dạng khoá của bảng ánh xạ: bỏ khoảng trắng hai đầu, chữ thường, khoảng trắng thành `_`."""
    # Chưa xác nhận `model.names` của ImageNet viết "horizontal bar" hay "horizontal_bar" (spec §6 ý 6, Q1);
    # chuẩn hoá để cả hai cách viết đều khớp khoá của bảng.
    return name.strip().lower().replace(" ", "_")
