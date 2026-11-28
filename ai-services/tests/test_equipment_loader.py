"""Test nạp model thiết bị (AIEC-05, 07, 08, 12, 14): nạp lười, dự phòng, lỗi nạp 503, registry, adapter ultralytics.

Quy ước theo spec docs/features/ai-equipment-classify.md §5: `GYM27`, `P`, `FakeClassifier`, `install`, `FT`
(= `_ft()`, tạo mới mỗi lần vì `seen` giữ trạng thái), `FT_PREDS`, `IMG`, `UP`, `URL`, `WEIGHTS`
(= `_weights(tmp_path)`), OK-BODY (= `_assert_ok_body`) và ERR (= `_assert_err_body`).
Helper chép từ test_equipment_api.py theo spec §6 ý 13 (helper nằm trong file test, không import chéo).
Không import ultralytics/torch thật: AIEC-14 thay module `ultralytics` bằng module giả trong `sys.modules`.
"""

import io
import logging
import sys
import time
import types
from collections.abc import Callable, Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from PIL import Image

from app.contracts import EQUIPMENT_LABELS, AiClassifyResult
from app.core.config import get_settings
from app.core.models import registry
from app.equipment import loader as equipment_loader
from app.equipment.loader import (
    get_equipment_model,
    load_yolo_classifier,
    register_equipment_model,
    reset_equipment_model,
)

GYM27 = EQUIPMENT_LABELS
URL = "/equipment-recognition/classify"
MAX_RETURNED_PREDICTIONS = 5
OK_BODY_KEYS = {"model_name", "model_version", "latency_ms", "predictions"}
PREDICTION_KEYS = {"label", "confidence"}
ERROR_KEYS = {"code", "message", "details", "request_id"}
UNAVAILABLE_MESSAGE = "Model nhận diện thiết bị chưa sẵn sàng"
# Chuỗi nội bộ của các ca AIEC-08 không được lộ ra message 503.
LEAKED_INTERNALS = ("best.pt", "secret", "ultralytics", "RuntimeError", "cable_machine")
FT_PREDS = [
    {"label": "cable_crossover_machine", "confidence": 0.9234},
    {"label": "lat_pulldown_machine", "confidence": 0.0512},
    {"label": "seated_cable_row_machine", "confidence": 0.0154},
    {"label": "dumbbell", "confidence": 0.006},
    {"label": "barbell", "confidence": 0.003},
]


def P(**overrides: float) -> dict[str, float]:
    """Phân phối toàn 0 trên 27 nhãn, ghi đè bằng `overrides` (tên theo quy ước spec §5)."""
    return {**dict.fromkeys(GYM27, 0.0), **overrides}


FT_PROBS = P(cable_crossover_machine=0.92341, lat_pulldown_machine=0.05123, seated_cable_row_machine=0.0154,
             dumbbell=0.006, barbell=0.003, treadmill=0.0012)


class FakeClassifier:
    """Model giả cùng giao diện `RawClassifier`: ghi `(mode, size)` của từng ảnh vào `seen`, trả bản sao `probs`."""

    def __init__(self, class_names: tuple[str, ...], probs: Mapping[str, float], delay: float = 0.0,
                 error: Exception | None = None) -> None:
        self.class_names = tuple(class_names)
        self.probs = dict(probs)
        self.delay = delay
        self.error = error
        self.seen: list[tuple[str, tuple[int, int]]] = []

    def predict_proba(self, image: Image.Image) -> dict[str, float]:
        self.seen.append((image.mode, image.size))
        time.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return dict(self.probs)


def _ft() -> FakeClassifier:
    """`FT` của spec: model fine-tune giả đủ 27 lớp."""
    return FakeClassifier(GYM27, FT_PROBS)


def _weights(tmp_path: Path) -> Path:
    """`WEIGHTS` của spec: vị trí trọng số fine-tune dưới `MODELS_DIR` giả."""
    return tmp_path / "equipment" / "best.pt"


def _create_weights(tmp_path: Path) -> None:
    _weights(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    _weights(tmp_path).write_bytes(b"fake-weights")


# 5 tham số (vượt ngưỡng 4 của coding-standards §1): chữ ký do spec §5 chốt để mọi test của module gọi giống nhau.
def install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *outcomes: object, finetuned: bool = True,
            load_delay: float = 0.0) -> list[str]:
    """Trỏ `MODELS_DIR` về `tmp_path`, thay `load_yolo_classifier` bằng hàm giả trả lần lượt `outcomes`.

    Hàm giả ghi `str(weights)` vào list trả về, ngủ `load_delay`, rồi ném outcome nếu là exception, không thì
    trả outcome đó; hết outcome thì dùng lại outcome cuối.
    """
    monkeypatch.setattr(get_settings(), "MODELS_DIR", tmp_path)
    if finetuned:
        _create_weights(tmp_path)
    calls: list[str] = []

    def fake_load_yolo_classifier(weights: str) -> object:
        calls.append(str(weights))
        time.sleep(load_delay)
        outcome = outcomes[min(len(calls), len(outcomes)) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(equipment_loader, "load_yolo_classifier", fake_load_yolo_classifier)
    return calls


def IMG(fmt: str = "PNG", size: tuple[int, int] = (32, 24), mode: str = "RGB") -> bytes:
    """Bytes của `Image.new(mode, size)` lưu bằng Pillow theo định dạng `fmt`."""
    buffer = io.BytesIO()
    Image.new(mode, size).save(buffer, format=fmt)
    return buffer.getvalue()


def UP(data: bytes, name: str = "scan.png", ctype: str = "image/png") -> dict[str, tuple[str, bytes, str]]:
    """Tham số `files` của request: một part file tên `image`."""
    return {"image": (name, data, ctype)}


@pytest.fixture(autouse=True)
def reset_model() -> Iterator[None]:
    """Model nạp lười được cache cấp module; xoá trước và sau mỗi test để test không phụ thuộc thứ tự chạy."""
    reset_equipment_model()
    yield
    reset_equipment_model()


def _assert_ok_body(body: dict[str, Any]) -> None:
    """OK-BODY của spec §5: đúng 4 key, hợp lệ với hợp đồng, `latency_ms` nguyên, top-5 nhãn hợp lệ giảm dần."""
    assert set(body) == OK_BODY_KEYS
    AiClassifyResult.model_validate(body)
    _assert_latency_ms(body["latency_ms"])
    predictions = body["predictions"]
    assert len(predictions) <= MAX_RETURNED_PREDICTIONS
    assert [set(prediction) for prediction in predictions] == [PREDICTION_KEYS] * len(predictions)
    _assert_labels_unique_in_gym27([prediction["label"] for prediction in predictions])
    _assert_confidences_ranked([prediction["confidence"] for prediction in predictions])


def _assert_latency_ms(latency_ms: object) -> None:
    # `bool` là lớp con của `int` nhưng không phải số mili giây hợp lệ.
    assert isinstance(latency_ms, int)
    assert not isinstance(latency_ms, bool)
    assert latency_ms >= 0


def _assert_labels_unique_in_gym27(labels: list[str]) -> None:
    assert set(labels) <= set(GYM27)
    assert len(set(labels)) == len(labels)


def _assert_confidences_ranked(confidences: list[float]) -> None:
    assert confidences == sorted(confidences, reverse=True)
    assert all(0 < confidence <= 1 for confidence in confidences)
    assert all(round(confidence, 4) == confidence for confidence in confidences)


def _assert_err_body(res: Response, request_id: str) -> None:
    """ERR của spec §5: đúng tập key, `details` là list, `request_id` khớp header đã gửi, không lộ Traceback."""
    body = res.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == ERROR_KEYS
    assert isinstance(body["error"]["details"], list)
    assert body["error"]["request_id"] == request_id
    assert res.headers["X-Request-ID"] == request_id
    assert "Traceback" not in res.text


def _post_ok(client: TestClient) -> dict[str, Any]:
    """Gửi `UP(IMG())`, kiểm `200` + OK-BODY; trả body."""
    res = client.post(URL, files=UP(IMG()))
    assert res.status_code == 200, res.text
    body = res.json()
    _assert_ok_body(body)
    return body


def _health_models(client: TestClient) -> dict[str, str | None]:
    """Gọi `GET /health`, kiểm `200` + `status == "ok"`; trả `models`."""
    res = client.get("/health")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "ok"
    return body["models"]


def _assert_concurrent_load_shares_one_model(thread_count: int) -> None:
    """`thread_count` thread cùng lúc gọi `get_equipment_model()` đều nhận cùng một model fine-tune."""
    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        futures = [executor.submit(get_equipment_model) for _ in range(thread_count)]
        models = [future.result() for future in futures]
    assert all(model is models[0] for model in models)
    assert (models[0].model_name, models[0].model_version) == ("yolov8_cls_gym", "1.0.0")


@pytest.mark.tc("AIEC-05")
def test_get_equipment_model_lazy_cached_thread_safe_loads_once_per_reset(
        client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = install(monkeypatch, tmp_path, _ft(), load_delay=0.05)

    # (a) Khởi động và `/health` không nạp model.
    _health_models(client)
    assert calls == []
    # (b) 3 request chỉ nạp một lần.
    versions = [_post_ok(client)["model_version"] for _ in range(3)]
    assert versions == ["1.0.0"] * 3
    assert len(calls) == 1
    assert Path(calls[0]) == _weights(tmp_path)
    # (c) 4 thread cùng gọi sau khi reset: chỉ nạp thêm 1 lần, cùng một đối tượng.
    reset_equipment_model()
    _assert_concurrent_load_shares_one_model(4)
    assert len(calls) == 2
    # (d) Reset rồi request mới thì nạp lại.
    reset_equipment_model()
    _post_ok(client)
    assert len(calls) == 3


@pytest.mark.tc("AIEC-07")
def test_classify_without_finetuned_weights_uses_imagenet_fallback(
        client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fallback = FakeClassifier(
        ("tench", "barbell", "dumbbell", "horizontal bar", "parallel_bars"),
        {"tench": 0.6, "horizontal bar": 0.3, "dumbbell": 0.06, "parallel_bars": 0.04, "barbell": 0.0})
    calls = install(monkeypatch, tmp_path, fallback, finetuned=False)

    body = _post_ok(client)

    assert (body["model_name"], body["model_version"]) == ("yolov8n_cls_imagenet", "1.0.0-fallback")
    assert body["model_version"].endswith("-fallback")
    assert body["predictions"] == [
        {"label": "pull_up_bar", "confidence": 0.3},
        {"label": "dumbbell", "confidence": 0.06},
        {"label": "dip_station", "confidence": 0.04},
    ]
    assert calls == ["yolov8n-cls.pt"]
    assert all(Path(call) != _weights(tmp_path) for call in calls)
    assert _health_models(client)["equipment"] == "yolov8n_cls_imagenet@1.0.0-fallback"


@pytest.mark.tc("AIEC-07")
def test_classify_fallback_missing_mapped_classes_logs_warning_and_still_predicts(
        client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    install(monkeypatch, tmp_path, FakeClassifier(("tench", "barbell", "dumbbell"), {"tench": 0.9, "dumbbell": 0.1}),
            finetuned=False)

    body = _post_ok(client)

    assert body["predictions"] == [{"label": "dumbbell", "confidence": 0.1}]
    warnings = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
    assert any("horizontal_bar" in message and "parallel_bars" in message for message in warnings), warnings


def _gym27_with_renamed_class() -> tuple[str, ...]:
    return tuple("cable_machine" if label == "cable_crossover_machine" else label for label in GYM27)


# Mỗi ca trả `(outcomes, có tạo best.pt hay không)`; tạo trong test để model giả không mang trạng thái giữa các ca.
LOAD_FAILURE_CASES: dict[str, Callable[[], tuple[tuple[object, ...], bool]]] = {
    "1-loader-raises": lambda: ((RuntimeError("khong mo duoc C:/secret/best.pt"), _ft()), True),
    "2-missing-ab-wheel": lambda: ((FakeClassifier(GYM27[:-1], {}),), True),
    "3-renamed-class": lambda: ((FakeClassifier(_gym27_with_renamed_class(), {}),), True),
    "4-ultralytics-missing": lambda: ((ImportError("No module named 'ultralytics'"),), False),
}


def _assert_unavailable(res: Response) -> None:
    """`503 service_unavailable`, `details == []`, ERR với `req_aiec0008`, message chung không lộ chi tiết."""
    assert res.status_code == 503, res.text
    _assert_err_body(res, "req_aiec0008")
    error = res.json()["error"]
    assert error["code"] == "service_unavailable"
    assert error["details"] == []
    # Cùng một message cố định cho cả 4 ca.
    assert error["message"] == UNAVAILABLE_MESSAGE
    assert not [leak for leak in LEAKED_INTERNALS if leak in error["message"]]


@pytest.mark.tc("AIEC-08")
@pytest.mark.parametrize("case", list(LOAD_FAILURE_CASES))
def test_classify_model_load_failure_returns_service_unavailable(
        client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, case: str) -> None:
    outcomes, is_finetuned = LOAD_FAILURE_CASES[case]()
    calls = install(monkeypatch, tmp_path, *outcomes, finetuned=is_finetuned)
    register_equipment_model()

    _assert_unavailable(client.post(URL, files=UP(IMG()), headers={"X-Request-ID": "req_aiec0008"}))

    if is_finetuned:
        # `best.pt` có mà nạp lỗi thì không chuyển sang model dự phòng.
        assert calls
        assert all(Path(call) == _weights(tmp_path) for call in calls)
    else:
        assert calls == ["yolov8n-cls.pt"]
    assert registry.versions()["equipment"] is None
    assert _health_models(client)["equipment"] is None


@pytest.mark.tc("AIEC-08")
def test_classify_after_load_failure_retries_load_and_returns_predictions(
        client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    outcomes, _ = LOAD_FAILURE_CASES["1-loader-raises"]()
    calls = install(monkeypatch, tmp_path, *outcomes)
    register_equipment_model()
    headers = {"X-Request-ID": "req_aiec0008"}
    _assert_unavailable(client.post(URL, files=UP(IMG()), headers=headers))

    res = client.post(URL, files=UP(IMG()), headers=headers)

    # Lỗi nạp không bị cache: lần gửi thứ 2 nạp lại và thành công.
    assert res.status_code == 200, res.text
    _assert_ok_body(res.json())
    assert res.json()["predictions"] == FT_PREDS
    assert len(calls) == 2
    assert all(Path(call) == _weights(tmp_path) for call in calls)


def _equipment_status() -> tuple[str | None, bool]:
    status = registry.models["equipment"]
    return status.version, status.required


@pytest.mark.tc("AIEC-12")
def test_register_equipment_model_twice_registers_optional_unloaded_model(client: TestClient) -> None:
    register_equipment_model()
    first = _equipment_status()
    register_equipment_model()

    assert first == (None, False)
    assert _equipment_status() == first
    assert list(registry.models) == ["equipment"]
    res = client.get("/health")
    assert res.status_code == 200, res.text
    assert res.json()["models"] == {"equipment": None}


@pytest.mark.tc("AIEC-12")
def test_health_after_classify_with_registered_model_reports_loaded_version(
        client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    install(monkeypatch, tmp_path, _ft())
    register_equipment_model()

    _post_ok(client)

    assert _health_models(client) == {"equipment": "yolov8_cls_gym@1.0.0"}
    assert registry.models["equipment"].required is False


@pytest.mark.tc("AIEC-12")
def test_classify_without_prior_registration_marks_model_ready_as_optional(
        client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    install(monkeypatch, tmp_path, _ft())

    _post_ok(client)

    assert _equipment_status() == ("yolov8_cls_gym@1.0.0", False)


def _install_fake_ultralytics(monkeypatch: pytest.MonkeyPatch, names: dict[int, str],
                              values: list[float]) -> type:
    """Đặt module `ultralytics` giả vào `sys.modules`; trả lớp `FakeYOLO` (ghi `instances`, `predict_calls`)."""

    class FakeData:
        def tolist(self) -> list[float]:
            return values

    class FakeYOLO:
        instances: list[str] = []
        predict_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

        def __init__(self, weights: str) -> None:
            FakeYOLO.instances.append(weights)
            self.names = names

        def predict(self, *args: Any, **kwargs: Any) -> list[SimpleNamespace]:
            FakeYOLO.predict_calls.append((args, kwargs))
            return [SimpleNamespace(probs=SimpleNamespace(data=FakeData()))]

    fake_module = types.ModuleType("ultralytics")
    fake_module.YOLO = FakeYOLO
    monkeypatch.setitem(sys.modules, "ultralytics", fake_module)
    return FakeYOLO


@pytest.mark.tc("AIEC-14")
def test_load_yolo_classifier_with_fake_ultralytics_orders_classes_and_maps_probabilities(
        monkeypatch: pytest.MonkeyPatch) -> None:
    fake_yolo: Any = _install_fake_ultralytics(
        monkeypatch, {0: "barbell", 2: "horizontal bar", 1: "dumbbell"}, [0.1, 0.7, 0.2])
    img = Image.new("RGB", (8, 8))

    clf = load_yolo_classifier("w/best.pt")
    probabilities = clf.predict_proba(img)

    assert fake_yolo.instances == ["w/best.pt"]
    assert clf.class_names == ("barbell", "dumbbell", "horizontal bar")
    assert probabilities == {"barbell": 0.1, "dumbbell": 0.7, "horizontal bar": 0.2}
    assert len(fake_yolo.predict_calls) == 1
    args, kwargs = fake_yolo.predict_calls[0]
    assert (args[0] if args else kwargs["source"]) is img
    assert kwargs["verbose"] is False


@pytest.mark.tc("AIEC-14")
def test_classify_with_fake_ultralytics_and_finetuned_weights_returns_one_hot_label(
        client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    one_hot = [1.0 if label == "dumbbell" else 0.0 for label in GYM27]
    fake_yolo: Any = _install_fake_ultralytics(monkeypatch, dict(enumerate(GYM27)), one_hot)
    monkeypatch.setattr(get_settings(), "MODELS_DIR", tmp_path)
    _create_weights(tmp_path)

    body = _post_ok(client)

    assert body["model_version"] == "1.0.0"
    assert body["predictions"] == [{"label": "dumbbell", "confidence": 1.0}]
    assert Path(fake_yolo.instances[0]) == _weights(tmp_path)
