"""Unit test cho hậu xử lý `build_predictions` (AIEC-09) và bảng nhãn `app.equipment.labels` (AIEC-10).

Quy ước theo spec docs/features/ai-equipment-classify.md §5: `GYM27` = `EQUIPMENT_LABELS`; `P(**kw)` = dict gán
mọi nhãn trong `GYM27` bằng 0.0 rồi ghi đè bằng `kw`. Xác suất là dữ liệu giả lập, không cần model hay trọng số.
"""

import re
from pathlib import Path

import pytest

from app.contracts import EQUIPMENT_LABELS, AiPrediction
from app.equipment.labels import FINETUNED_LABEL_MAP, IMAGENET_FALLBACK_LABEL_MAP, normalize_class_name
from app.equipment.predictions import TOP_K, build_predictions

GYM27 = EQUIPMENT_LABELS
SEED_FILE = Path(__file__).resolve().parents[2] / "database/postgresql/seeds/02_reference.sql"
AI_LABEL_PATTERN = re.compile(r"\(\s*'[^']+'\s*,\s*'([^']+)'\s*,\s*'ai_label'\s*\)")

# Ca (A) của AIEC-09: vượt trần, nhãn lạ, tên trùng sau chuẩn hoá, hoà điểm, NaN, vô cực, số âm, làm tròn về 0,
# và một nhãn hợp lệ đứng thứ 6 (`plyo_box`).
RAW_PROBABILITIES_A = {
    "cable_crossover_machine": 1.0000003, "khong_co_nhan": 0.99, "Dumbbell ": 0.3, "DUMBBELL": 0.25,
    "flat_bench": 0.2, "barbell": 0.2, "kettlebell": float("nan"), "treadmill": float("inf"),
    "power_rack": 0.04996, "jump_rope": 0.00004, "ab_wheel": -0.1, "plyo_box": 0.01,
}
EXPECTED_A = [("cable_crossover_machine", 1.0), ("dumbbell", 0.3), ("barbell", 0.2), ("flat_bench", 0.2),
              ("power_rack", 0.05)]
RAW_PROBABILITIES_B = {"tench": 0.5, "Horizontal Bar": 0.3, "parallel_bars": 0.1, "dumbbell": 0.02, "barbell": 0.01}
EXPECTED_B = [("pull_up_bar", 0.3), ("dip_station", 0.1), ("dumbbell", 0.02), ("barbell", 0.01)]


def P(**overrides: float) -> dict[str, float]:
    """Phân phối toàn 0 trên 27 nhãn, ghi đè bằng `overrides` (tên theo quy ước spec §5)."""
    return {**dict.fromkeys(GYM27, 0.0), **overrides}


def _as_pairs(predictions: list[AiPrediction]) -> list[tuple[str, float]]:
    assert all(isinstance(prediction, AiPrediction) for prediction in predictions)
    return [(prediction.label, prediction.confidence) for prediction in predictions]


@pytest.mark.tc("AIEC-09")
def test_top_k_default_is_five() -> None:
    assert TOP_K == 5


@pytest.mark.tc("AIEC-09")
def test_build_predictions_noisy_finetuned_output_returns_clean_top_five() -> None:
    predictions = build_predictions(RAW_PROBABILITIES_A, FINETUNED_LABEL_MAP)

    assert _as_pairs(predictions) == EXPECTED_A


@pytest.mark.tc("AIEC-09")
def test_build_predictions_imagenet_classes_returns_mapped_ai_labels() -> None:
    predictions = build_predictions(RAW_PROBABILITIES_B, IMAGENET_FALLBACK_LABEL_MAP)

    assert _as_pairs(predictions) == EXPECTED_B


@pytest.mark.tc("AIEC-09")
def test_build_predictions_empty_probabilities_returns_empty_list() -> None:
    assert build_predictions({}, FINETUNED_LABEL_MAP) == []


@pytest.mark.tc("AIEC-09")
def test_build_predictions_all_zero_probabilities_returns_empty_list() -> None:
    probabilities = P()

    assert len(probabilities) == 27
    assert build_predictions(probabilities, FINETUNED_LABEL_MAP) == []


@pytest.mark.tc("AIEC-09")
def test_build_predictions_custom_top_k_returns_first_items_of_default_ranking() -> None:
    predictions = build_predictions(RAW_PROBABILITIES_A, FINETUNED_LABEL_MAP, top_k=2)

    assert _as_pairs(predictions) == [("cable_crossover_machine", 1.0), ("dumbbell", 0.3)]


@pytest.mark.tc("AIEC-10")
def test_seed_ai_labels_match_equipment_labels() -> None:
    seed_labels = AI_LABEL_PATTERN.findall(SEED_FILE.read_text(encoding="utf-8"))

    assert len(seed_labels) == 27
    assert set(seed_labels) == set(EQUIPMENT_LABELS)


@pytest.mark.tc("AIEC-10")
def test_finetuned_label_map_maps_each_label_to_itself() -> None:
    assert FINETUNED_LABEL_MAP == {label: label for label in EQUIPMENT_LABELS}
    assert len(FINETUNED_LABEL_MAP) == 27


@pytest.mark.tc("AIEC-10")
def test_imagenet_fallback_label_map_targets_only_equipment_labels() -> None:
    assert IMAGENET_FALLBACK_LABEL_MAP == {
        "barbell": "barbell", "dumbbell": "dumbbell", "horizontal_bar": "pull_up_bar", "parallel_bars": "dip_station",
    }
    assert set(IMAGENET_FALLBACK_LABEL_MAP.values()) <= set(EQUIPMENT_LABELS)


@pytest.mark.tc("AIEC-10")
def test_normalize_class_name_padded_mixed_case_returns_snake_case() -> None:
    assert normalize_class_name(" Horizontal Bar ") == "horizontal_bar"
