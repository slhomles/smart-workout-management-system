"""Test cho `POST /equipment-recognition/classify` (AIEC-01–04, 06, 11, 13, 15): HTTP qua fixture `client`,
`classify_image` gọi thẳng, đăng ký lúc import và OpenAPI.

Quy ước theo spec docs/features/ai-equipment-classify.md §5: `GYM27`, `P`, `FakeClassifier`, `install`, `FT`
(= fixture `ft`, tạo mới mỗi test vì `seen` giữ trạng thái), `FT_PREDS`, `IMG`, `UP`, `URL`, `WEIGHTS`
(= `_weights(tmp_path)`), OK-BODY (= `_assert_ok_body`) và ERR (= `_assert_err_body`).
Model thật được thay bằng `FakeClassifier` qua `install`: không cần ultralytics/torch, trọng số hay mạng.
"""

import ast
import io
import json
import logging
import random
import subprocess
import sys
import threading
import time
from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from PIL import Image

from app.contracts import EQUIPMENT_LABELS, AiClassifyResult
from app.core.config import get_settings
from app.equipment import loader as equipment_loader
from app.equipment.labels import FINETUNED_LABEL_MAP
from app.equipment.loader import reset_equipment_model
from app.equipment.predictions import build_predictions
from app.equipment.service import classify_image
from app.main import create_app

GYM27 = EQUIPMENT_LABELS
URL = "/equipment-recognition/classify"
TEN_MIB = 10 * 1024 * 1024
MAX_RETURNED_PREDICTIONS = 5
OK_BODY_KEYS = {"model_name", "model_version", "latency_ms", "predictions"}
PREDICTION_KEYS = {"label", "confidence"}
ERROR_KEYS = {"code", "message", "details", "request_id"}
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


# Xác suất của `FT`: `treadmill` đứng thứ 6 nên bị cắt khỏi top-5.
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


def _weights(tmp_path: Path) -> Path:
    """`WEIGHTS` của spec: vị trí trọng số fine-tune dưới `MODELS_DIR` giả."""
    return tmp_path / "equipment" / "best.pt"


# 5 tham số (vượt ngưỡng 4 của coding-standards §1): chữ ký do spec §5 chốt để mọi test của module gọi giống nhau.
def install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *outcomes: object, finetuned: bool = True,
            load_delay: float = 0.0) -> list[str]:
    """Trỏ `MODELS_DIR` về `tmp_path`, thay `load_yolo_classifier` bằng hàm giả trả lần lượt `outcomes`.

    Hàm giả ghi `str(weights)` vào list trả về, ngủ `load_delay`, rồi ném outcome nếu là exception, không thì
    trả outcome đó; hết outcome thì dùng lại outcome cuối.
    """
    monkeypatch.setattr(get_settings(), "MODELS_DIR", tmp_path)
    if finetuned:
        _weights(tmp_path).parent.mkdir(parents=True, exist_ok=True)
        _weights(tmp_path).write_bytes(b"fake-weights")
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


@pytest.fixture
def ft() -> FakeClassifier:
    """`FT` của spec: model fine-tune giả đủ 27 lớp."""
    return FakeClassifier(GYM27, FT_PROBS)


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


def _post_image_ok(client: TestClient, files: dict[str, Any], case: str) -> dict[str, Any]:
    """Gửi ảnh hợp lệ, kiểm `200` + OK-BODY + `predictions == FT_PREDS`; trả body."""
    res = client.post(URL, files=files)

    assert res.status_code == 200, (case, res.text)
    body = res.json()
    _assert_ok_body(body)
    assert body["predictions"] == FT_PREDS, case
    return body


def _jpeg_rotated_by_exif() -> bytes:
    """JPEG RGB 40×20 kèm EXIF Orientation = 6 (ảnh chụp điện thoại cần xoay 90 độ)."""
    exif = Image.Exif()
    exif[0x0112] = 6
    buffer = io.BytesIO()
    Image.new("RGB", (40, 20)).save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def _truncated_jpeg() -> bytes:
    """Nửa đầu bytes của một JPEG 64×64 nhiễu: header đọc được nhưng dữ liệu ảnh bị cắt cụt."""
    buffer = io.BytesIO()
    Image.effect_noise((64, 64), 40).convert("RGB").save(buffer, format="JPEG", quality=95)
    data = buffer.getvalue()
    return data[: len(data) // 2]


def _png_padded_to(total_bytes: int) -> bytes:
    """`IMG()` nối thêm byte 0x00 cho đủ đúng `total_bytes`."""
    data = IMG()
    return data + b"\x00" * (total_bytes - len(data))


@pytest.mark.tc("AIEC-01")
def test_classify_png_with_finetuned_model_returns_top_five_and_request_id(
        client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, ft: FakeClassifier) -> None:
    calls = install(monkeypatch, tmp_path, ft)

    res = client.post(URL, files=UP(IMG()), data={"note": "x"}, headers={"X-Request-ID": "req_aiec0001"})

    assert res.status_code == 200, res.text
    assert res.headers["X-Request-ID"] == "req_aiec0001"
    body = res.json()
    _assert_ok_body(body)
    assert (body["model_name"], body["model_version"]) == ("yolov8_cls_gym", "1.0.0")
    # `treadmill` (0.0012) đứng thứ 6 nên bị cắt; field form thừa `note` bị bỏ qua.
    assert body["predictions"] == FT_PREDS
    assert ft.seen == [("RGB", (32, 24))]
    assert len(calls) == 1
    assert Path(calls[0]) == _weights(tmp_path)


def _aiec02_uploads() -> list[tuple[str, dict[str, Any]]]:
    return [
        ("a-jpeg", UP(IMG("JPEG"), "a.jpg", "image/jpeg")),
        ("b-webp", UP(IMG("WEBP"), "a.webp", "image/webp")),
        ("c-rgba", UP(IMG(mode="RGBA"))),
        ("d-grayscale", UP(IMG(mode="L"))),
        ("e-palette", UP(IMG(mode="P"))),
        ("f-exif-orientation-6", UP(_jpeg_rotated_by_exif(), "a.jpg", "image/jpeg")),
        ("g-png-declared-jpeg", UP(IMG(), "a.jpg", "image/jpeg")),
        ("h-octet-stream", UP(IMG("JPEG"), "blob", "application/octet-stream")),
    ]


@pytest.mark.tc("AIEC-02")
def test_classify_each_accepted_format_or_mode_returns_rgb_predictions_with_one_model_load(
        client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, ft: FakeClassifier) -> None:
    calls = install(monkeypatch, tmp_path, ft)

    for case, files in _aiec02_uploads():
        _post_image_ok(client, files, case)

    assert len(ft.seen) == 8
    assert [mode for mode, _ in ft.seen] == ["RGB"] * 8
    # Ca (f) 40×20 đã xoay theo EXIF Orientation = 6 nên thành 20×40.
    assert [size for _, size in ft.seen] == [(32, 24)] * 5 + [(20, 40)] + [(32, 24)] * 2
    # Model nạp một lần rồi dùng lại cho cả 8 request.
    assert len(calls) == 1


def _aiec03_invalid_uploads() -> list[tuple[str, dict[str, Any]]]:
    return [
        ("1-empty", UP(b"", "a.jpg", "image/jpeg")),
        ("2-not-an-image", UP(b"khong-phai-anh")),
        ("3-gif", UP(IMG("GIF", (8, 8)), "a.gif", "image/gif")),
        ("4-bmp-declared-png", UP(IMG("BMP", (8, 8)))),
        ("5-truncated-jpeg", UP(_truncated_jpeg(), "a.jpg", "image/jpeg")),
        ("6-over-10-mib", UP(b"\xff" * (TEN_MIB + 1), "big.jpg", "image/jpeg")),
    ]


def _assert_bad_image(res: Response, case: str) -> None:
    """`400 bad_request` + ERR với `req_aiec0003` + `details` trỏ vào field `image`."""
    assert res.status_code == 400, (case, res.text)
    _assert_err_body(res, "req_aiec0003")
    error = res.json()["error"]
    assert error["code"] == "bad_request", case
    assert "image" in [detail["field"] for detail in error["details"]], case


@pytest.mark.tc("AIEC-03")
def test_classify_invalid_image_content_returns_bad_request_before_loading_model(
        client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, ft: FakeClassifier) -> None:
    calls = install(monkeypatch, tmp_path, ft)
    headers = {"X-Request-ID": "req_aiec0003"}

    for case, files in _aiec03_invalid_uploads():
        _assert_bad_image(client.post(URL, files=files, headers=headers), case)
    with monkeypatch.context() as patch:
        # Ảnh 32×24 = 768 điểm ảnh vượt 2 × 100 nên Pillow coi là bom giải nén.
        patch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
        _assert_bad_image(client.post(URL, files=UP(IMG()), headers=headers), "7-decompression-bomb")

    # Ảnh được kiểm trước khi nạp model: 7 ca lỗi không gọi loader, không chạy suy luận.
    assert calls == []
    assert ft.seen == []
    # Ca đối chứng (8): đúng 10 MiB vẫn hợp lệ.
    _post_image_ok(client, UP(_png_padded_to(TEN_MIB)), "8-exactly-10-mib")


def _aiec04_malformed_requests() -> list[tuple[str, dict[str, Any]]]:
    return [
        ("1-form-without-file", {"data": {"foo": "bar"}}),
        ("2-json-body", {"json": {"image": "abc"}}),
        ("3-text-field-not-file", {"data": {"image": "abc"}}),
        # Ngoài spec: cùng ca (3) nhưng gửi đúng kiểu multipart, part `image` không có filename nên là văn bản.
        ("3-extra-multipart-text-part", {"files": {"image": (None, b"abc")}}),
        ("4-no-body", {}),
    ]


def _assert_image_validation_error(res: Response, case: str) -> None:
    """`422 validation_error` + ERR với `req_aiec0004` + `details[].field` chứa `image`."""
    assert res.status_code == 422, (case, res.text)
    _assert_err_body(res, "req_aiec0004")
    error = res.json()["error"]
    assert error["code"] == "validation_error", case
    assert "image" in [detail["field"] for detail in error["details"]], case


def _assert_framework_error(res: Response, status_code: int) -> None:
    assert res.status_code == status_code, res.text
    _assert_err_body(res, "req_aiec0004")
    assert res.json()["error"]["code"] == f"http_{status_code}"


@pytest.mark.tc("AIEC-04")
def test_classify_malformed_request_or_wrong_route_returns_framework_error_without_loading(
        client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, ft: FakeClassifier) -> None:
    calls = install(monkeypatch, tmp_path, ft)
    headers = {"X-Request-ID": "req_aiec0004"}

    for case, request_kwargs in _aiec04_malformed_requests():
        _assert_image_validation_error(client.post(URL, headers=headers, **request_kwargs), case)
    _assert_framework_error(client.get(URL, headers=headers), 405)
    # Route nội bộ không có tiền tố `/api/v1` (06 §2).
    _assert_framework_error(client.post(f"/api/v1{URL}", files=UP(IMG()), headers=headers), 404)

    assert calls == []
    assert ft.seen == []


class _ConcurrencyProbe(FakeClassifier):
    """`probe` của AIEC-06a: `FakeClassifier` đếm số lời gọi `predict_proba` đang chạy cùng lúc."""

    def __init__(self, class_names: tuple[str, ...], probs: Mapping[str, float], delay: float) -> None:
        super().__init__(class_names, probs, delay=delay)
        self.active = 0
        self.max_active = 0
        self._counter_lock = threading.Lock()

    def predict_proba(self, image: Image.Image) -> dict[str, float]:
        with self._counter_lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            return super().predict_proba(image)
        finally:
            with self._counter_lock:
                self.active -= 1


@pytest.mark.tc("AIEC-06")
def test_classify_image_from_concurrent_threads_runs_inference_one_at_a_time(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    probe = _ConcurrencyProbe(GYM27, FT_PROBS, delay=0.02)
    install(monkeypatch, tmp_path, probe)

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: classify_image(IMG()), range(4)))

    assert len(results) == 4
    for result in results:
        assert isinstance(result, AiClassifyResult)
        assert result.model_dump(mode="json")["predictions"] == FT_PREDS
    assert probe.max_active == 1


@pytest.mark.tc("AIEC-06")
def test_classify_first_request_with_slow_model_load_reports_inference_latency_only(
        client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    install(monkeypatch, tmp_path, FakeClassifier(GYM27, FT_PROBS, delay=0.02), load_delay=0.3)

    res = client.post(URL, files=UP(IMG()))

    assert res.status_code == 200, res.text
    # Suy luận ngủ 20 ms, nạp model ngủ 300 ms: `latency_ms` < 300 chứng tỏ không tính thời gian nạp.
    assert 15 <= res.json()["latency_ms"] < 300


def _post_finetuned_ok(client: TestClient) -> list[dict[str, Any]]:
    """Gửi `UP(IMG())`, kiểm `200` + OK-BODY + `model_version == "1.0.0"`; trả `predictions`."""
    res = client.post(URL, files=UP(IMG()))

    assert res.status_code == 200, res.text
    body = res.json()
    _assert_ok_body(body)
    assert body["model_version"] == "1.0.0"
    predictions: list[dict[str, Any]] = body["predictions"]
    return predictions


def _random_distribution(rng: random.Random) -> dict[str, float]:
    weights = [rng.random() for _ in GYM27]
    total = sum(weights)
    return {label: weight / total for label, weight in zip(GYM27, weights)}


@pytest.mark.tc("AIEC-11")
def test_classify_various_distributions_returns_valid_ranked_top_five(
        client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = FakeClassifier(GYM27, P())
    install(monkeypatch, tmp_path, fake)

    # (1) Phân phối đều 1/27 ≈ 0.037: hoà nên xếp theo `label` tăng dần.
    fake.probs = dict.fromkeys(GYM27, 1 / 27)
    tied_labels = ["ab_wheel", "adjustable_bench", "barbell", "cable_crossover_machine", "chest_press_machine"]
    assert _post_finetuned_ok(client) == [{"label": label, "confidence": 0.037} for label in tied_labels]
    # (2) Chắc chắn một nhãn; (3) toàn 0 nên không còn nhãn nào.
    fake.probs = P(treadmill=1.0)
    assert _post_finetuned_ok(client) == [{"label": "treadmill", "confidence": 1.0}]
    fake.probs = P()
    assert _post_finetuned_ok(client) == []
    # (4) 20 phân phối ngẫu nhiên, seed cố định để test tất định.
    rng = random.Random(2026)
    for _ in range(20):
        fake.probs = _random_distribution(rng)
        predictions = _post_finetuned_ok(client)
        expected = [p.model_dump() for p in build_predictions(fake.probs, FINETUNED_LABEL_MAP)]
        assert predictions == expected
        assert len(predictions) == 5


AI_SERVICES_DIR = Path(__file__).resolve().parents[1]
HEAVY_PACKAGES = frozenset({"ultralytics", "torch", "torchvision", "cv2"})
REGISTRY_PROBE_CODE = (
    "import json, sys, app.main; from app.core.models import registry; s = registry.models['equipment']; "
    "print(json.dumps({'version': s.version, 'required': s.required, 'heavy': sorted(m for m in "
    "('ultralytics', 'torch', 'torchvision', 'cv2') if m in sys.modules)}))"
)


@pytest.mark.tc("AIEC-13")
def test_import_app_main_registers_equipment_unloaded_without_heavy_libraries() -> None:
    # Tiến trình con: `sys.modules` và registry sạch, không bị các test khác trong process này ảnh hưởng.
    completed = subprocess.run([sys.executable, "-c", REGISTRY_PROBE_CODE], cwd=AI_SERVICES_DIR,
                               capture_output=True, text=True, timeout=60, check=True)

    last_line = completed.stdout.strip().splitlines()[-1]
    assert json.loads(last_line) == {"version": None, "required": False, "heavy": []}


def _import_roots(node: ast.Import | ast.ImportFrom) -> set[str]:
    if isinstance(node, ast.Import):
        return {alias.name.split(".")[0] for alias in node.names}
    # Import tương đối (`from . import x`) luôn thuộc gói `app`, không phải thư viện nặng.
    if node.level or node.module is None:
        return set()
    return {node.module.split(".")[0]}


def _collect_heavy_imports(node: ast.AST, is_in_function: bool, found: list[tuple[int, bool]]) -> None:
    """Ghi `(lineno, is_in_function)` cho mọi import thư viện nặng dưới `node`, mang theo cờ tổ tiên là hàm."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.Import, ast.ImportFrom)) and _import_roots(child) & HEAVY_PACKAGES:
            found.append((child.lineno, is_in_function))
        is_function = isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        _collect_heavy_imports(child, is_in_function or is_function, found)


@pytest.mark.tc("AIEC-13")
def test_equipment_sources_import_heavy_libraries_only_inside_functions() -> None:
    heavy_imports: dict[str, list[tuple[int, bool]]] = {}
    for source in sorted((AI_SERVICES_DIR / "app" / "equipment").rglob("*.py")):
        found: list[tuple[int, bool]] = []
        _collect_heavy_imports(ast.parse(source.read_text(encoding="utf-8")), False, found)
        heavy_imports[source.name] = found

    module_level = {name: [line for line, is_in_function in found if not is_in_function]
                    for name, found in heavy_imports.items()}
    assert all(lines == [] for lines in module_level.values()), module_level
    # Đối chứng: `loader.py` import ultralytics trong hàm, nên test thực sự tìm thấy import nặng để kiểm.
    assert any(heavy_imports.values())


def _resolve_schema(openapi: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if ref is None:
        return schema
    resolved: dict[str, Any] = openapi["components"]["schemas"][ref.rsplit("/", 1)[-1]]
    return resolved


@pytest.mark.tc("AIEC-13")
def test_openapi_documents_classify_as_multipart_post_returning_ai_classify_result(client: TestClient) -> None:
    res = client.get("/openapi.json")

    assert res.status_code == 200, res.text
    openapi = res.json()
    path_item = openapi["paths"][URL]
    assert set(path_item) == {"post"}
    operation = path_item["post"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"].endswith("/AiClassifyResult")
    request_content = operation["requestBody"]["content"]
    assert "multipart/form-data" in request_content
    form_schema = _resolve_schema(openapi, request_content["multipart/form-data"]["schema"])
    assert "image" in form_schema["required"]
    assert form_schema["properties"]["image"]["format"] == "binary"
    assert not [path for path in openapi["paths"] if path.startswith("/api/v1")]


@pytest.mark.tc("AIEC-15")
def test_classify_when_inference_raises_returns_internal_error_without_details(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    install(monkeypatch, tmp_path, FakeClassifier(GYM27, P(), error=RuntimeError("chi tiet noi bo model")))

    # Như test_errors.py: không ném lại lỗi server vào test, để thấy đúng response 500 mà client nhận.
    with TestClient(create_app(), raise_server_exceptions=False) as raw_client:
        res = raw_client.post(URL, files=UP(IMG()), headers={"X-Request-ID": "req_aiec0015"})

    assert res.status_code == 500, res.text
    _assert_err_body(res, "req_aiec0015")
    assert res.json()["error"]["code"] == "internal_error"
    assert "chi tiet noi bo model" not in res.text


@pytest.mark.tc("AIEC-15")
def test_classify_logs_never_contain_file_names_or_image_bytes(
        client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, ft: FakeClassifier,
        caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    install(monkeypatch, tmp_path, ft)

    ok = client.post(URL, files=UP(IMG("JPEG"), "nguyen-van-a.jpg", "image/jpeg"))
    bad = client.post(URL, files=UP(b"khong-phai-anh", "tran-thi-b.png"))

    assert (ok.status_code, bad.status_code) == (200, 400)
    private_fragments = ("nguyen-van-a", "tran-thi-b", "khong-phai-anh")
    for record in caplog.records:
        logged_text = record.getMessage() + str(record.args)
        assert not [fragment for fragment in private_fragments if fragment in logged_text], record.name
