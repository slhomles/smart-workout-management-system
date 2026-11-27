"""Test HTTP cho `POST /recovery/predict` (AIRP-01, 02, 03, 04, 12) qua fixture `client`.

Quy ước theo spec docs/features/ai-recovery-predict.md §5: `T0`, `BODY` (= `_body`), `L` (= `_muscle_load`),
`DOC`, `MULTI` và OK-BODY (= `_assert_ok_body`). UUID trong body là dữ liệu giả lập lấy từ ví dụ
06-ai-contracts.md §2.3.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple

import pytest
from fastapi.testclient import TestClient

from app.contracts import RecoveryPredictionOutput
from app.core.models import registry

PREDICT_PATH = "/recovery/predict"
T0 = "2026-11-27T01:00:00Z"
PREDICTION_KEYS = {"muscle_group_id", "fatigue_score", "recovered_at"}
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
