"""Test HTTP cho `POST /recovery/predict` (AIRP-01, 02, 03, 04, 06, 07, 08, 09, 12) qua fixture `client`.

Quy ước theo spec docs/features/ai-recovery-predict.md §5: `T0`, `BODY` (= `_body`), `L` (= `_muscle_load`),
`DOC`, `MULTI`, OK-BODY (= `_assert_ok_body`) và ERR (= `_assert_err_body`). UUID trong body là dữ liệu giả lập
lấy từ ví dụ 06-ai-contracts.md §2.3.
"""

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.contracts import RecoveryPredictionOutput
from app.core.models import registry

PREDICT_PATH = "/recovery/predict"
T0 = "2026-11-27T01:00:00Z"
PREDICTION_KEYS = {"muscle_group_id", "fatigue_score", "recovered_at"}
ERROR_KEYS = {"code", "message", "details", "request_id"}
# Tiến trình con cần cwd là thư mục gốc ai-services để `import app.main` chạy được (spec §6 ý 12).
AI_SERVICES_DIR = Path(__file__).resolve().parents[1]
PRINT_REGISTRY_SCRIPT = ("import json, app.main; from app.core.models import registry; "
                         "print(json.dumps(registry.versions()))")


class LoadCase(NamedTuple):
    """Các tham số của `L(id, eff, vol, rpe, base)` trong spec §5; `rpe` có thể là None (null)."""

    muscle_group_id: int
    effective_sets: float
    weighted_volume_kg: float
    avg_rpe: float | None
    base_recovery_hours: int


def _muscle_load(case: LoadCase, direct_sets: int = 4, total_reps: int = 40) -> dict[str, Any]:
    return {"muscle_group_id": case.muscle_group_id, "direct_sets": direct_sets,
            "effective_sets": case.effective_sets, "total_reps": total_reps,
            "weighted_volume_kg": case.weighted_volume_kg, "avg_rpe": case.avg_rpe,
            "base_recovery_hours": case.base_recovery_hours}


def _body(loads: list[dict[str, Any]], trained_at: str = T0) -> dict[str, Any]:
    return {"session_id": "7c1e9a52-3b8d-4f60-a2e4-9d5b1c7f3a10", "user_id": "00000000-0000-0000-0000-000000000003",
            "trained_at": trained_at, "muscle_loads": loads}


DOC = _body([_muscle_load(LoadCase(1, 5.5, 2400.0, 8.0, 72))])
MULTI = _body([_muscle_load(LoadCase(13, 4.0, 2000.0, 8.0, 60)), _muscle_load(LoadCase(1, 2.4, 1800.0, None, 60)),
               _muscle_load(LoadCase(7, 12.0, 6000.0, 10.0, 72)), _muscle_load(LoadCase(20, 0.5, 10000.0, 8.0, 48)),
               _muscle_load(LoadCase(22, 0.0, 0.0, 8.0, 36))])
CHEST_LOAD = LoadCase(13, 4.0, 2000.0, 8.0, 60)


def _assert_ok_body(body: dict[str, Any]) -> None:
    """OK-BODY của spec §5: đúng tập key, hợp lệ với hợp đồng, mọi `recovered_at` là UTC hậu tố `Z`."""
    predictions = body["predictions"]
    assert set(body) == {"model_version", "predictions"}
    assert [set(prediction) for prediction in predictions] == [PREDICTION_KEYS] * len(predictions)
    RecoveryPredictionOutput.model_validate(body)
    assert [prediction["recovered_at"][-1] for prediction in predictions] == ["Z"] * len(predictions)


def _post_predict_ok(client: TestClient, body: dict[str, Any]) -> list[tuple[float, str]]:
    """Gửi body, kiểm `200` + OK-BODY, trả các cặp (`fatigue_score`, `recovered_at`) theo thứ tự trả về."""
    res = client.post(PREDICT_PATH, json=body)

    assert res.status_code == 200, res.text
    payload = res.json()
    _assert_ok_body(payload)
    assert payload["model_version"] == "heuristic-v1"
    return [(prediction["fatigue_score"], prediction["recovered_at"]) for prediction in payload["predictions"]]


def _doc_with(root: dict[str, Any] | None = None, load: dict[str, Any] | None = None) -> dict[str, Any]:
    """Bản sao sâu của `DOC` có ghi đè/thêm key ở gốc và ở phần tử tải đầu, để không làm hỏng `DOC` dùng chung."""
    body = copy.deepcopy(DOC)
    body.update(root or {})
    body["muscle_loads"][0].update(load or {})
    return body


def _doc_without(key: str) -> dict[str, Any]:
    """Bản sao sâu của `DOC` bỏ đúng 1 key ở gốc."""
    body = copy.deepcopy(DOC)
    del body[key]
    return body


def _doc_load_without(key: str) -> dict[str, Any]:
    """Bản sao sâu của `DOC` bỏ đúng 1 key của phần tử tải đầu."""
    body = copy.deepcopy(DOC)
    del body["muscle_loads"][0][key]
    return body


def _assert_err_body(res: Response, request_id: str) -> None:
    """ERR của spec §5: đúng tập key, `details` là list, `request_id` khớp header đã gửi, không lộ Traceback."""
    body = res.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == ERROR_KEYS
    assert isinstance(body["error"]["details"], list)
    assert body["error"]["request_id"] == request_id
    assert res.headers["X-Request-ID"] == request_id
    assert "Traceback" not in res.text


def _validation_error_fields(res: Response, request_id: str) -> list[str | None]:
    """Kiểm `422 validation_error` + ERR + `details` không rỗng; trả danh sách `details[].field`."""
    assert res.status_code == 422, res.text
    _assert_err_body(res, request_id)
    error = res.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"] != []
    return [detail["field"] for detail in error["details"]]


@pytest.mark.tc("AIRP-01")
def test_predict_contract_example_returns_locked_body_and_request_id(client: TestClient) -> None:
    res = client.post(PREDICT_PATH, json=DOC, headers={"X-Request-ID": "req_airp0001"})

    assert res.status_code == 200
    assert res.headers["X-Request-ID"] == "req_airp0001"
    # 55,0 điểm hiệp (10 × 5,5 × 8/8) + 12,0 điểm volume (2400/200) = 67,0; phục hồi 72 × 1,17 = 84,24 giờ.
    assert res.json() == {
        "model_version": "heuristic-v1",
        "predictions": [{"muscle_group_id": 1, "fatigue_score": 67.0, "recovered_at": "2026-11-30T13:14:24Z"}],
    }
    _assert_ok_body(res.json())


@pytest.mark.tc("AIRP-02")
def test_predict_multiple_muscle_groups_returns_one_prediction_each_in_request_order(client: TestClient) -> None:
    res = client.post(PREDICT_PATH, json=MULTI)

    assert res.status_code == 200
    body = res.json()
    _assert_ok_body(body)
    assert body["model_version"] == "heuristic-v1"
    assert [prediction["muscle_group_id"] for prediction in body["predictions"]] == [13, 1, 7, 20, 22]
    assert [(prediction["fatigue_score"], prediction["recovered_at"]) for prediction in body["predictions"]] == [
        (50.0, "2026-11-29T13:00:00Z"),
        (30.0, "2026-11-29T01:00:00Z"),  # avg_rpe null nên dùng RPE 7
        (100.0, "2026-12-01T13:00:00Z"),  # chặn trần 100
        (25.0, "2026-11-28T13:00:00Z"),  # điểm volume chặn ở 20
        (0.0, "2026-11-27T19:00:00Z"),
    ]


@pytest.mark.tc("AIRP-03")
@pytest.mark.parametrize(("load", "expected"), [
    pytest.param(_muscle_load(LoadCase(13, 4.0, 0.0, 6.0, 60)), (30.0, "2026-11-29T01:00:00Z"), id="a-rpe-6"),
    pytest.param(_muscle_load(LoadCase(13, 4.0, 0.0, 10.0, 60)), (50.0, "2026-11-29T13:00:00Z"), id="b-rpe-10"),
    pytest.param(_muscle_load(LoadCase(13, 4.0, 0.0, None, 60)), (35.0, "2026-11-29T04:00:00Z"), id="c-rpe-null"),
    pytest.param(_muscle_load(CHEST_LOAD, direct_sets=1, total_reps=0), (50.0, "2026-11-29T13:00:00Z"),
                 id="d-few-direct-sets-reps"),
    pytest.param(_muscle_load(CHEST_LOAD, direct_sets=30, total_reps=500), (50.0, "2026-11-29T13:00:00Z"),
                 id="e-many-direct-sets-reps"),
])
def test_predict_rpe_or_unused_fields_change_returns_expected_score_and_time(
        client: TestClient, load: dict[str, Any], expected: tuple[float, str]) -> None:
    # (d) và (e) cho cùng kết quả vì `heuristic-v1` không dùng `direct_sets`, `total_reps` (spec §6 ý 6).
    assert _post_predict_ok(client, _body([load])) == [expected]


@pytest.mark.tc("AIRP-04")
@pytest.mark.parametrize(("trained_at", "expected_recovered_at"), [
    pytest.param("2026-11-27T08:00:00+07:00", "2026-11-29T13:00:00Z", id="a-plus-07"),
    pytest.param("2026-11-27T01:00:00-05:00", "2026-11-29T18:00:00Z", id="b-minus-05"),
    pytest.param("2020-01-01T00:00:00Z", "2020-01-03T12:00:00Z", id="c-past-not-now"),
])
def test_predict_any_timezone_or_past_trained_at_returns_utc_time_from_trained_at(
        client: TestClient, trained_at: str, expected_recovered_at: str) -> None:
    body = _body([_muscle_load(CHEST_LOAD)], trained_at)

    assert _post_predict_ok(client, body) == [(50.0, expected_recovered_at)]


@pytest.mark.tc("AIRP-12")
def test_import_app_main_in_new_process_registers_recovery_model() -> None:
    result = subprocess.run([sys.executable, "-c", PRINT_REGISTRY_SCRIPT], cwd=AI_SERVICES_DIR,
                            capture_output=True, text=True, timeout=60, check=True)

    versions = json.loads(result.stdout.strip().splitlines()[-1])

    # Chỉ kiểm khoá `recovery`: module AI khác sau này cũng đăng ký model của mình lúc import.
    assert versions.get("recovery") == "heuristic-v1"


@pytest.mark.tc("AIRP-12")
def test_predict_with_empty_registry_returns_ok_without_registering(client: TestClient) -> None:
    assert registry.models == {}

    res = client.post(PREDICT_PATH, json=DOC)

    assert res.status_code == 200
    body = res.json()
    _assert_ok_body(body)
    assert body["model_version"] == "heuristic-v1"
    # Endpoint không đọc cũng không ghi registry: heuristic luôn sẵn sàng nên không bao giờ trả 503.
    assert registry.models == {}


# Body thành công của AIRP-01, dùng lại cho AIRP-06(b): field thừa không được làm đổi kết quả.
DOC_RESPONSE_BODY = {
    "model_version": "heuristic-v1",
    "predictions": [{"muscle_group_id": 1, "fatigue_score": 67.0, "recovered_at": "2026-11-30T13:14:24Z"}],
}
AIRP07_HEADERS = {"X-Request-ID": "req_airp0007"}
AIRP08_HEADERS = {"X-Request-ID": "req_airp0008"}
AIRP09_HEADERS = {"X-Request-ID": "req_airp0009"}
# Giá trị biên hợp lệ của AIRP-08(b): RPE 1 và 10, base 12 và 168 giờ, mọi số đếm bằng 0.
BOUNDARY_LOADS = [_muscle_load(LoadCase(2, 0.0, 0.0, 1.0, 12), direct_sets=0, total_reps=0),
                  _muscle_load(LoadCase(3, 0.0, 0.0, 10.0, 168), direct_sets=0, total_reps=0)]
DUPLICATE_MUSCLE_LOADS = [_muscle_load(LoadCase(1, 4.0, 2000.0, 8.0, 60)),
                          _muscle_load(LoadCase(1, 2.0, 0.0, 8.0, 60))]


@pytest.mark.tc("AIRP-06")
def test_predict_empty_muscle_loads_returns_empty_predictions(client: TestClient) -> None:
    res = client.post(PREDICT_PATH, json=_body([]))

    assert res.status_code == 200, res.text
    assert res.json() == {"model_version": "heuristic-v1", "predictions": []}
    _assert_ok_body(res.json())


@pytest.mark.tc("AIRP-06")
def test_predict_extra_fields_returns_contract_example_body(client: TestClient) -> None:
    body = _doc_with(root={"note": "x"}, load={"source": "manual"})

    res = client.post(PREDICT_PATH, json=body)

    assert res.status_code == 200, res.text
    assert res.json() == DOC_RESPONSE_BODY


@pytest.mark.tc("AIRP-07")
@pytest.mark.parametrize(("body", "expected_field", "expected_code"), [
    pytest.param(_doc_without("trained_at"), "trained_at", "missing", id="1-missing-trained-at"),
    pytest.param(_doc_with(root={"trained_at": "2026-11-27T01:00:00"}), "trained_at", "timezone_aware",
                 id="2-naive-trained-at"),
    pytest.param(_doc_with(root={"session_id": "abc"}), "session_id", "uuid_parsing", id="3-invalid-session-id"),
    pytest.param(_doc_without("user_id"), "user_id", "missing", id="4-missing-user-id"),
    pytest.param(_doc_without("muscle_loads"), "muscle_loads", "missing", id="5-missing-muscle-loads"),
    pytest.param(_doc_load_without("base_recovery_hours"), "muscle_loads.0.base_recovery_hours", "missing",
                 id="6-missing-base-recovery-hours"),
    # `avg_rpe` được phép null nhưng key vẫn bắt buộc, giống `MuscleLoad.avg_rpe` của hợp đồng.
    pytest.param(_doc_load_without("avg_rpe"), "muscle_loads.0.avg_rpe", "missing", id="7-missing-avg-rpe-key"),
])
def test_predict_malformed_body_returns_validation_error_on_field(
        client: TestClient, body: dict[str, Any], expected_field: str, expected_code: str) -> None:
    res = client.post(PREDICT_PATH, json=body, headers=AIRP07_HEADERS)

    _validation_error_fields(res, "req_airp0007")
    details = res.json()["error"]["details"]
    assert (expected_field, expected_code) in [(detail["field"], detail["code"]) for detail in details]


@pytest.mark.tc("AIRP-07")
def test_predict_without_body_returns_validation_error(client: TestClient) -> None:
    res = client.post(PREDICT_PATH, headers=AIRP07_HEADERS)

    _validation_error_fields(res, "req_airp0007")


@pytest.mark.tc("AIRP-07")
def test_get_predict_path_returns_method_not_allowed(client: TestClient) -> None:
    res = client.get(PREDICT_PATH, headers=AIRP07_HEADERS)

    assert res.status_code == 405
    _assert_err_body(res, "req_airp0007")
    assert res.json()["error"]["code"] == "http_405"


@pytest.mark.tc("AIRP-08")
@pytest.mark.parametrize(("field", "value"), [
    pytest.param("base_recovery_hours", 11, id="1-base-recovery-hours-below-12"),
    pytest.param("base_recovery_hours", 169, id="2-base-recovery-hours-above-168"),
    pytest.param("avg_rpe", 0.5, id="3-avg-rpe-below-1"),
    pytest.param("avg_rpe", 10.5, id="4-avg-rpe-above-10"),
    pytest.param("effective_sets", -0.1, id="5-negative-effective-sets"),
    pytest.param("weighted_volume_kg", -1, id="6-negative-weighted-volume-kg"),
    pytest.param("direct_sets", -1, id="7-negative-direct-sets"),
    pytest.param("total_reps", -1, id="8-negative-total-reps"),
    pytest.param("muscle_group_id", 0, id="9-muscle-group-id-zero"),
    # Ngoài 9 ca của spec: cận trên smallint của `catalog.muscle_groups.id`.
    pytest.param("muscle_group_id", 32768, id="extra-muscle-group-id-above-smallint"),
])
def test_predict_load_value_outside_db_limit_returns_validation_error_on_field(
        client: TestClient, field: str, value: float) -> None:
    res = client.post(PREDICT_PATH, json=_doc_with(load={field: value}), headers=AIRP08_HEADERS)

    # So bằng cả danh sách: đúng 1 lỗi, đường dẫn không có hậu tố kiểu union (vd `avg_rpe.float`).
    assert _validation_error_fields(res, "req_airp0008") == [f"muscle_loads.0.{field}"]


@pytest.mark.tc("AIRP-08")
def test_predict_boundary_load_values_returns_ok(client: TestClient) -> None:
    res = client.post(PREDICT_PATH, json=_body(BOUNDARY_LOADS))

    assert res.status_code == 200, res.text
    body = res.json()
    _assert_ok_body(body)
    # Mệt 0 nên phục hồi 0,5 × base: 6 giờ và 84 giờ sau T0.
    assert body["predictions"] == [
        {"muscle_group_id": 2, "fatigue_score": 0.0, "recovered_at": "2026-11-27T07:00:00Z"},
        {"muscle_group_id": 3, "fatigue_score": 0.0, "recovered_at": "2026-11-30T13:00:00Z"},
    ]


@pytest.mark.tc("AIRP-09")
@pytest.mark.parametrize(("field", "literal"), [
    pytest.param("effective_sets", "NaN", id="1-nan-effective-sets"),
    pytest.param("weighted_volume_kg", "Infinity", id="2-infinity-weighted-volume-kg"),
])
def test_predict_non_finite_load_number_returns_validation_error_on_field(
        client: TestClient, field: str, literal: str) -> None:
    # `json.dumps` ghi float không hữu hạn thành literal JS `NaN`/`Infinity`, đúng JSON thô mà spec yêu cầu gửi.
    raw_body = json.dumps(_doc_with(load={field: float(literal)}))
    assert f'"{field}": {literal}' in raw_body

    res = client.post(PREDICT_PATH, content=raw_body,
                      headers={"Content-Type": "application/json", **AIRP09_HEADERS})

    assert res.status_code != 500
    assert f"muscle_loads.0.{field}" in _validation_error_fields(res, "req_airp0009")


@pytest.mark.tc("AIRP-09")
@pytest.mark.parametrize(("body", "expected_field"), [
    pytest.param(_body(DUPLICATE_MUSCLE_LOADS), "muscle_loads", id="3-duplicate-muscle-group-id"),
    pytest.param(_doc_with(root={"trained_at": "9999-12-31T23:00:00Z"}), "trained_at",
                 id="4-recovery-time-overflow"),
    # Ngoài 4 ca của spec: đổi sang UTC đã tràn (năm 0) trước cả phép cộng giờ phục hồi.
    pytest.param(_doc_with(root={"trained_at": "0001-01-01T00:00:00+01:00"}), "trained_at",
                 id="extra-utc-conversion-overflow"),
])
def test_predict_duplicate_muscle_group_or_time_overflow_returns_validation_error_on_field(
        client: TestClient, body: dict[str, Any], expected_field: str) -> None:
    res = client.post(PREDICT_PATH, json=body, headers=AIRP09_HEADERS)

    assert res.status_code != 500
    assert expected_field in _validation_error_fields(res, "req_airp0009")
