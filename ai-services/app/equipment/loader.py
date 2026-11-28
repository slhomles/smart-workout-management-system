"""Nạp lười model phân loại thiết bị và báo sổ đăng ký `/health` (spec ai-equipment-classify §6 ý 5, 9).

Có `MODELS_DIR/equipment/best.pt` thì dùng YOLOv8-cls fine-tune trên 27 nhãn của 06-ai-contracts.md §2.5;
không có thì dùng YOLOv8n-cls ImageNet làm model dự phòng, `model_version` hậu tố `-fallback` (06 §2.4).
`ultralytics`/`torch` chỉ được import bên trong `load_yolo_classifier` (ai-services/README.md).
"""

import logging
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from PIL import Image

from app.contracts import EQUIPMENT_LABELS
from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.core.models import registry
from app.equipment.labels import FINETUNED_LABEL_MAP, IMAGENET_FALLBACK_LABEL_MAP, normalize_class_name

logger = logging.getLogger(__name__)

MODEL_KEY = "equipment"
MODEL_NAME = "yolov8_cls_gym"
MODEL_VERSION = "1.0.0"
FINETUNED_WEIGHTS = Path("equipment") / "best.pt"
FALLBACK_MODEL_NAME = "yolov8n_cls_imagenet"
FALLBACK_MODEL_VERSION = "1.0.0-fallback"
FALLBACK_WEIGHTS = "yolov8n-cls.pt"
# Một message chung cho mọi lỗi nạp: không lộ đường dẫn, tên lớp exception hay tên thư viện (Claude_api_respone §3).
MODEL_UNAVAILABLE_MESSAGE = "Model nhận diện thiết bị chưa sẵn sàng"


class RawClassifier(Protocol):
    """Giao diện tối thiểu của bộ phân loại: tên lớp và xác suất theo tên lớp cho một ảnh RGB."""

    class_names: tuple[str, ...]

    def predict_proba(self, image: Image.Image) -> Mapping[str, float]:
        """Trả xác suất của từng lớp trong `class_names` cho ảnh."""
        ...


@dataclass(frozen=True)
class EquipmentModel:
    """Model đang phục vụ: tên, phiên bản, bộ phân loại thô và bảng ánh xạ tên lớp sang `ai_label`."""

    model_name: str
    model_version: str
    classifier: RawClassifier
    label_map: Mapping[str, str]


class ClassListMismatchError(Exception):
    """Danh sách lớp của trọng số fine-tune không trùng đúng 27 nhãn của 06-ai-contracts.md §2.5."""


class _UltralyticsClassifier:
    """Bọc model YOLOv8-cls của ultralytics về giao diện `RawClassifier`."""

    def __init__(self, model: Any) -> None:
        self._model = model
        # `model.names` là dict chỉ số lớp → tên; sắp theo chỉ số để khớp thứ tự vector xác suất.
        self.class_names: tuple[str, ...] = tuple(name for _, name in sorted(model.names.items()))

    def predict_proba(self, image: Image.Image) -> Mapping[str, float]:
        """Chạy model trên một ảnh, trả xác suất theo tên lớp."""
        result = self._model.predict(image, verbose=False)[0]
        values = result.probs.data.tolist()
        return dict(zip(self.class_names, values))


def load_yolo_classifier(weights: str) -> RawClassifier:
    """Nạp YOLOv8-cls từ `weights` (đường dẫn hoặc tên trọng số ultralytics) và bọc về `RawClassifier`."""
    # Import trong hàm: ultralytics kéo theo torch, nặng và không có trong môi trường test/CI (ai-services/README.md).
    from ultralytics import YOLO

    return _UltralyticsClassifier(YOLO(weights))


_load_lock = threading.Lock()
_loaded_model: EquipmentModel | None = None


def get_equipment_model() -> EquipmentModel:
    """Trả model đã nạp; lần đầu thì nạp (fine-tune hoặc dự phòng) và báo registry. Lỗi nạp → 503."""
    global _loaded_model
    # Kiểm ngoài khoá trước để request sau khi đã nạp không phải xếp hàng chờ khoá.
    if _loaded_model is not None:
        return _loaded_model
    with _load_lock:
        # Kiểm lại trong khoá: thread khác có thể vừa nạp xong khi thread này đang chờ (nạp đúng một lần).
        if _loaded_model is None:
            model = _load_equipment_model()
            _mark_ready(model)
            _loaded_model = model
        return _loaded_model


def reset_equipment_model() -> None:
    """Xoá model đã cache để lần gọi sau nạp lại (dùng trong test); không đụng registry."""
    global _loaded_model
    with _load_lock:
        _loaded_model = None


def register_equipment_model() -> None:
    """Đăng ký khoá `equipment` vào registry, không bắt buộc; gọi nhiều lần không đổi gì."""
    # `required=False` vì model nạp lười: nếu bắt buộc thì `/health` trả 503 cho tới request phân loại đầu tiên.
    registry.register(MODEL_KEY, required=False)


def _load_equipment_model() -> EquipmentModel:
    # Tính đường dẫn lúc nạp, không lúc import, để đổi `MODELS_DIR` (cấu hình, test) có hiệu lực.
    weights_path = get_settings().MODELS_DIR / FINETUNED_WEIGHTS
    try:
        model = _load_finetuned(weights_path) if weights_path.is_file() else _load_fallback()
    # Mọi lỗi nạp (thiếu thư viện, trọng số hỏng, sai danh sách lớp) đều là "model chưa sẵn sàng" với backend.
    # Không cache lỗi: request sau thử nạp lại. Chỉ ghi tên lớp exception vì message có thể chứa đường dẫn.
    except Exception as exc:
        logger.warning("equipment model load failed: %s", type(exc).__name__)
        raise ServiceUnavailableError(MODEL_UNAVAILABLE_MESSAGE) from exc
    logger.info("equipment model loaded: %s@%s", model.model_name, model.model_version)
    return model


def _load_finetuned(weights_path: Path) -> EquipmentModel:
    # `best.pt` có mà hỏng thì để lỗi lộ ra (503), không lặng lẽ chuyển sang dự phòng: 06 §2.4 chỉ cho dùng
    # dự phòng khi không có trọng số (spec §6 ý 5, Q7).
    classifier = load_yolo_classifier(str(weights_path))
    _ensure_contract_classes(classifier.class_names)
    return EquipmentModel(MODEL_NAME, MODEL_VERSION, classifier, FINETUNED_LABEL_MAP)


def _ensure_contract_classes(class_names: tuple[str, ...]) -> None:
    # 06 §2.5: danh sách lớp PHẢI trùng đúng 27 nhãn; so chính xác, không chuẩn hoá, để lộ trọng số huấn luyện sai.
    if len(class_names) == len(EQUIPMENT_LABELS) and sorted(class_names) == sorted(EQUIPMENT_LABELS):
        return
    missing_count = len(set(EQUIPMENT_LABELS) - set(class_names))
    logger.warning("fine-tuned equipment model has %d classes, %d contract labels missing",
                   len(class_names), missing_count)
    raise ClassListMismatchError("fine-tuned classes do not match contract labels")


def _load_fallback() -> EquipmentModel:
    classifier = load_yolo_classifier(FALLBACK_WEIGHTS)
    _warn_unmapped_fallback_classes(classifier.class_names)
    return EquipmentModel(FALLBACK_MODEL_NAME, FALLBACK_MODEL_VERSION, classifier, IMAGENET_FALLBACK_LABEL_MAP)


def _warn_unmapped_fallback_classes(class_names: tuple[str, ...]) -> None:
    # Tên lớp ImageNet thật chưa được xác nhận (spec Q1); thiếu lớp thì vẫn chạy, chỉ báo để người vận hành biết.
    known_names = {normalize_class_name(name) for name in class_names}
    missing = sorted(key for key in IMAGENET_FALLBACK_LABEL_MAP if key not in known_names)
    if missing:
        logger.warning("fallback equipment model lacks mapped classes: %s", ", ".join(missing))


def _mark_ready(model: EquipmentModel) -> None:
    # `mark_ready` tự tạo khoá với `required=True` nếu chưa đăng ký, nên đăng ký `required=False` trước.
    registry.register(MODEL_KEY, required=False)
    registry.mark_ready(MODEL_KEY, f"{model.model_name}@{model.model_version}")
