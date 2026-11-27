"""Unit test cho thuật toán `heuristic-v1` (AIRP-10) và việc đăng ký model `recovery` (AIRP-11).

Quy ước theo spec docs/features/ai-recovery-predict.md §5: `T0`, `BODY` (= `_body`), `L` (= `_muscle_load`).
UUID trong body là dữ liệu giả lập lấy từ ví dụ 06-ai-contracts.md §2.3.
"""

import copy
import itertools
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple

import pytest
from fastapi.testclient import TestClient

from app.contracts import PredictedRecovery, RecoveryPredictionOutput
from app.core.models import registry
from app.recovery.heuristic import predict_recovery, register_recovery_model
from app.recovery.schemas import RecoveryPredictRequest

T0 = "2026-11-27T01:00:00Z"
T0_UTC = datetime(2026, 11, 27, 1, 0, tzinfo=timezone.utc)
DEFAULT_MUSCLE_GROUP_ID = 1

EFFECTIVE_SETS_GRID = (0, 0.5, 3, 8, 12, 40)
WEIGHTED_VOLUME_KG_GRID = (0, 500, 4000, 100000)
AVG_RPE_GRID = (None, 1.0, 6.5, 10.0)
ORDERED_AVG_RPE = (1.0, 6.5, 10.0)
BASE_RECOVERY_HOURS_GRID = (12, 60, 168)
GRID_SIZE = 6 * 4 * 4 * 3


class LoadCase(NamedTuple):
    """Các field của một phần tử tải mà `heuristic-v1` dùng khi tính."""

    effective_sets: float
    weighted_volume_kg: float
    avg_rpe: float | None
    base_recovery_hours: int


def _body(loads: list[dict[str, Any]], trained_at: str = T0) -> dict[str, Any]:
    return {"session_id": "7c1e9a52-3b8d-4f60-a2e4-9d5b1c7f3a10", "user_id": "00000000-0000-0000-0000-000000000003",
            "trained_at": trained_at, "muscle_loads": loads}


def _muscle_load(case: LoadCase, muscle_group_id: int = DEFAULT_MUSCLE_GROUP_ID) -> dict[str, Any]:
    return {"muscle_group_id": muscle_group_id, "direct_sets": 4, "effective_sets": case.effective_sets,
            "total_reps": 40, "weighted_volume_kg": case.weighted_volume_kg, "avg_rpe": case.avg_rpe,
            "base_recovery_hours": case.base_recovery_hours}


def _predict_single(case: LoadCase, trained_at: str = T0) -> PredictedRecovery:
    request = RecoveryPredictRequest.model_validate(_body([_muscle_load(case)], trained_at))
    output = predict_recovery(request)
    assert output.model_version == "heuristic-v1"
    assert [prediction.muscle_group_id for prediction in output.predictions] == [DEFAULT_MUSCLE_GROUP_ID]
    return output.predictions[0]


def _adjacent_pairs(cases: list[LoadCase], field: str, ordered_values: tuple[Any, ...]) -> list[tuple[LoadCase, LoadCase]]:
    """Cặp tổ hợp chỉ khác nhau ở `field`, với giá trị liền kề tăng dần trong `ordered_values`."""
    return [(case, case._replace(**{field: higher}))
            for case in cases
            for lower, higher in itertools.pairwise(ordered_values)
            if getattr(case, field) == lower]


def _score_decreases(grid: dict[LoadCase, PredictedRecovery],
                     pairs: list[tuple[LoadCase, LoadCase]]) -> list[tuple[LoadCase, LoadCase]]:
    return [(lower, higher) for lower, higher in pairs if grid[higher].fatigue_score < grid[lower].fatigue_score]


@pytest.fixture(scope="module")
def grid_predictions() -> dict[LoadCase, PredictedRecovery]:
    """Kết quả `predict_recovery` cho đủ lưới tổ hợp của AIRP-10, mỗi tổ hợp gọi với 1 phần tử tải."""
    grid = itertools.product(EFFECTIVE_SETS_GRID, WEIGHTED_VOLUME_KG_GRID, AVG_RPE_GRID, BASE_RECOVERY_HOURS_GRID)
    return {LoadCase(*values): _predict_single(LoadCase(*values)) for values in grid}


@pytest.mark.tc("AIRP-10")
def test_predict_recovery_doc_example_returns_locked_score_and_time() -> None:
    request = RecoveryPredictRequest.model_validate(_body([_muscle_load(LoadCase(5.5, 2400.0, 8.0, 72))]))

    output = predict_recovery(request)

    assert isinstance(output, RecoveryPredictionOutput)
    assert output.model_dump(mode="json") == {
        "model_version": "heuristic-v1",
        "predictions": [{"muscle_group_id": 1, "fatigue_score": 67.0, "recovered_at": "2026-11-30T13:14:24Z"}],
    }


@pytest.mark.tc("AIRP-10")
def test_predict_recovery_multiple_loads_keeps_input_order_and_values() -> None:
    loads = [_muscle_load(LoadCase(4.0, 2000.0, 8.0, 60), 13), _muscle_load(LoadCase(2.4, 1800.0, None, 60), 1),
             _muscle_load(LoadCase(12.0, 6000.0, 10.0, 72), 7), _muscle_load(LoadCase(0.5, 10000.0, 8.0, 48), 20),
             _muscle_load(LoadCase(0.0, 0.0, 8.0, 36), 22)]

    output = predict_recovery(RecoveryPredictRequest.model_validate(_body(loads)))

    assert output.model_dump(mode="json")["predictions"] == [
        {"muscle_group_id": 13, "fatigue_score": 50.0, "recovered_at": "2026-11-29T13:00:00Z"},
        {"muscle_group_id": 1, "fatigue_score": 30.0, "recovered_at": "2026-11-29T01:00:00Z"},
        {"muscle_group_id": 7, "fatigue_score": 100.0, "recovered_at": "2026-12-01T13:00:00Z"},
        {"muscle_group_id": 20, "fatigue_score": 25.0, "recovered_at": "2026-11-28T13:00:00Z"},
        {"muscle_group_id": 22, "fatigue_score": 0.0, "recovered_at": "2026-11-27T19:00:00Z"},
    ]


@pytest.mark.tc("AIRP-10")
def test_predict_recovery_any_grid_load_returns_score_in_range_with_one_decimal(
        grid_predictions: dict[LoadCase, PredictedRecovery]) -> None:
    scores = {case: prediction.fatigue_score for case, prediction in grid_predictions.items()}

    assert len(scores) == GRID_SIZE == 288
    assert [case for case, score in scores.items() if not 0 <= score <= 100] == []
    assert [case for case, score in scores.items() if round(score, 1) != score] == []
    assert (min(scores.values()), max(scores.values())) == (0.0, 100.0)


@pytest.mark.tc("AIRP-10")
def test_predict_recovery_any_grid_load_recovers_within_half_to_one_and_half_base(
        grid_predictions: dict[LoadCase, PredictedRecovery]) -> None:
    earliest = {case: T0_UTC + timedelta(hours=0.5 * case.base_recovery_hours) for case in grid_predictions}
    latest = {case: T0_UTC + timedelta(hours=1.5 * case.base_recovery_hours) for case in grid_predictions}

    outside = [case for case, prediction in grid_predictions.items()
               if not earliest[case] <= prediction.recovered_at <= latest[case]]

    assert outside == []
    assert grid_predictions[LoadCase(0, 0, None, 60)].recovered_at == earliest[LoadCase(0, 0, None, 60)]
    assert grid_predictions[LoadCase(40, 100000, 10.0, 168)].recovered_at == latest[LoadCase(40, 100000, 10.0, 168)]


@pytest.mark.tc("AIRP-10")
def test_predict_recovery_any_grid_load_returns_recovered_at_in_utc(
        grid_predictions: dict[LoadCase, PredictedRecovery]) -> None:
    not_utc = [case for case, prediction in grid_predictions.items()
               if prediction.recovered_at.utcoffset() != timedelta(0)]
    same_instant_in_plus_seven = _predict_single(LoadCase(4.0, 2000.0, 8.0, 60), "2026-11-27T08:00:00+07:00")

    assert not_utc == []
    assert same_instant_in_plus_seven.recovered_at.utcoffset() == timedelta(0)
    assert same_instant_in_plus_seven.recovered_at == datetime(2026, 11, 29, 13, 0, tzinfo=timezone.utc)


@pytest.mark.tc("AIRP-10")
def test_predict_recovery_more_sets_or_volume_never_lowers_score(
        grid_predictions: dict[LoadCase, PredictedRecovery]) -> None:
    cases = list(grid_predictions)
    sets_pairs = _adjacent_pairs(cases, "effective_sets", EFFECTIVE_SETS_GRID)
    volume_pairs = _adjacent_pairs(cases, "weighted_volume_kg", WEIGHTED_VOLUME_KG_GRID)

    # 5 cặp liền kề của effective_sets × 48 tổ hợp còn lại; 3 cặp của weighted_volume_kg × 72.
    assert (len(sets_pairs), len(volume_pairs)) == (240, 216)
    assert _score_decreases(grid_predictions, sets_pairs) == []
    assert _score_decreases(grid_predictions, volume_pairs) == []


@pytest.mark.tc("AIRP-10")
def test_predict_recovery_higher_rpe_never_lowers_score(grid_predictions: dict[LoadCase, PredictedRecovery]) -> None:
    rpe_pairs = _adjacent_pairs(list(grid_predictions), "avg_rpe", ORDERED_AVG_RPE)

    # 2 cặp liền kề (1.0 → 6.5 → 10.0, không gồm null) × 72 tổ hợp còn lại.
    assert len(rpe_pairs) == 144
    assert _score_decreases(grid_predictions, rpe_pairs) == []


@pytest.mark.tc("AIRP-10")
def test_predict_recovery_higher_score_same_base_never_recovers_earlier(
        grid_predictions: dict[LoadCase, PredictedRecovery]) -> None:
    by_base = {base: sorted((prediction.fatigue_score, prediction.recovered_at)
                            for case, prediction in grid_predictions.items() if case.base_recovery_hours == base)
               for base in BASE_RECOVERY_HOURS_GRID}

    earlier_after_higher_score = {base: [(lower, higher) for lower, higher in itertools.pairwise(ordered)
                                         if higher[1] < lower[1]]
                                  for base, ordered in by_base.items()}

    assert [len(ordered) for ordered in by_base.values()] == [96, 96, 96]
    assert earlier_after_higher_score == {12: [], 60: [], 168: []}


@pytest.mark.tc("AIRP-11")
def test_register_recovery_model_called_twice_keeps_single_required_ready_entry() -> None:
    assert registry.models == {}

    register_recovery_model()
    assert registry.versions() == {"recovery": "heuristic-v1"}
    assert registry.models["recovery"].required is True
    state_after_first_call = copy.deepcopy(registry.models)

    register_recovery_model()

    assert registry.models == state_after_first_call
    assert registry.versions() == {"recovery": "heuristic-v1"}
    assert registry.models["recovery"].required is True


@pytest.mark.tc("AIRP-11")
def test_health_after_registering_recovery_model_returns_ok_with_version(client: TestClient) -> None:
    register_recovery_model()
    register_recovery_model()

    res = client.get("/health")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["models"] == {"recovery": "heuristic-v1"}
