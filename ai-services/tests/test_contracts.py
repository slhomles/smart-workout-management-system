"""Ví dụ trong docs/architecture/06-ai-contracts.md §2 phải hợp lệ với model hợp đồng, và tập field
phải khớp schema backend (backend/app/schemas/recovery.py, equipment_scan.py)."""

import pytest
from pydantic import ValidationError

from app.contracts import (
    EQUIPMENT_LABELS,
    AiClassifyResult,
    MuscleLoad,
    PredictedRecovery,
    RecoveryPredictionInput,
    RecoveryPredictionOutput,
)

RECOVERY_INPUT = {
    "session_id": "7c1e9a52-3b8d-4f60-a2e4-9d5b1c7f3a10",
    "user_id": "00000000-0000-0000-0000-000000000003",
    "trained_at": "2026-11-27T01:00:00Z",
    "muscle_loads": [{"muscle_group_id": 1, "direct_sets": 4, "effective_sets": 5.5, "total_reps": 40,
                      "weighted_volume_kg": 2400.0, "avg_rpe": 8.0, "base_recovery_hours": 72}],
}
RECOVERY_OUTPUT = {"model_version": "heuristic-v1",
                   "predictions": [{"muscle_group_id": 1, "fatigue_score": 80.0, "recovered_at": "2026-11-29T13:00:00Z"}]}
CLASSIFY_OUTPUT = {"model_name": "yolov8_cls_gym", "model_version": "1.0.0", "latency_ms": 180,
                   "predictions": [{"label": "cable_crossover_machine", "confidence": 0.9234}]}


def test_doc_examples_are_valid() -> None:
    RecoveryPredictionInput.model_validate(RECOVERY_INPUT)
    RecoveryPredictionOutput.model_validate(RECOVERY_OUTPUT)
    AiClassifyResult.model_validate(CLASSIFY_OUTPUT)


def test_field_names_match_backend_schemas() -> None:
    assert set(MuscleLoad.model_fields) == {"muscle_group_id", "direct_sets", "effective_sets", "total_reps",
                                            "weighted_volume_kg", "avg_rpe", "base_recovery_hours"}
    assert set(RecoveryPredictionInput.model_fields) == {"session_id", "user_id", "trained_at", "muscle_loads"}
    assert set(PredictedRecovery.model_fields) == {"muscle_group_id", "fatigue_score", "recovered_at"}
    assert set(AiClassifyResult.model_fields) == {"model_name", "model_version", "latency_ms", "predictions"}


@pytest.mark.parametrize("score", [-1, 100.5])
def test_fatigue_score_out_of_range_is_rejected(score: float) -> None:
    with pytest.raises(ValidationError):
        PredictedRecovery.model_validate({"muscle_group_id": 1, "fatigue_score": score,
                                          "recovered_at": "2026-11-29T13:00:00Z"})


def test_recovered_at_requires_timezone() -> None:
    with pytest.raises(ValidationError):
        PredictedRecovery.model_validate({"muscle_group_id": 1, "fatigue_score": 10, "recovered_at": "2026-11-29T13:00:00"})


def test_classify_result_limits_predictions_to_twenty() -> None:
    preds = [{"label": "dumbbell", "confidence": 0.01}] * 21
    with pytest.raises(ValidationError):
        AiClassifyResult.model_validate({**CLASSIFY_OUTPUT, "predictions": preds})


def test_equipment_labels_are_unique_and_complete() -> None:
    assert len(EQUIPMENT_LABELS) == len(set(EQUIPMENT_LABELS)) == 27
