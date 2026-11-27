"""Unit test schema Pydantic của module video job (SRT-19) — không DB, không async."""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.video_job import CreateVideoJobRequest, VideoJobFailureRequest, VideoJobResultRequest

REPS3: list[dict[str, Any]] = [
    {
        "rep_no": 1, "start_offset_ms": 0, "eccentric_ms": 3000, "pause_bottom_ms": 200,
        "concentric_ms": 1000, "pause_top_ms": 300, "min_joint_angle_deg": 78.5,
        "max_joint_angle_deg": 172.0, "is_full_rom": True,
    },
    {
        "rep_no": 2, "start_offset_ms": 4600, "eccentric_ms": 2900, "pause_bottom_ms": 100,
        "concentric_ms": 1100, "pause_top_ms": 300,
    },
    {
        "rep_no": 3, "start_offset_ms": 9000, "eccentric_ms": 3100, "pause_bottom_ms": 0,
        "concentric_ms": 900, "pause_top_ms": 0, "is_full_rom": False,
    },
]


def res(media: uuid.UUID, reps: list[dict[str, Any]]) -> dict[str, Any]:
    """RES(media, reps) của spec §5, ở dạng dict để từng ca đổi một chỗ."""
    return {
        "model_name": "yolov8_pose",
        "model_version": "8.2.1",
        "result_video_media_id": media,
        "overall_score": 85,
        "correct_form_pct": 90,
        "feedback_summary": "Tempo đều, hạ chậm 3 giây",
        "rep_events": [dict(rep) for rep in reps],
    }


def _valid_reps(count: int) -> list[dict[str, Any]]:
    return [
        {"rep_no": n, "start_offset_ms": (n - 1) * 4000, "eccentric_ms": 2000, "concentric_ms": 1000}
        for n in range(1, count + 1)
    ]


def _set(field: str, value: Any) -> Callable[[dict[str, Any]], None]:
    def mutate(body: dict[str, Any]) -> None:
        body[field] = value

    return mutate


def _drop(field: str) -> Callable[[dict[str, Any]], None]:
    def mutate(body: dict[str, Any]) -> None:
        del body[field]

    return mutate


def _set_rep_numbers(numbers: list[int]) -> Callable[[dict[str, Any]], None]:
    def mutate(body: dict[str, Any]) -> None:
        body["rep_events"] = [{**rep, "rep_no": n} for rep, n in zip(_valid_reps(len(numbers)), numbers, strict=True)]

    return mutate


def _set_first_rep(**changes: Any) -> Callable[[dict[str, Any]], None]:
    def mutate(body: dict[str, Any]) -> None:
        body["rep_events"][0].update(changes)

    return mutate


# Ca (1)–(11) của SRT-19: (mã ca, cách đổi body, loc mong đợi của lỗi đầu; None = không ràng buộc loc).
RESULT_INVALID_CASES = [
    ("01_empty_model_name", _set("model_name", ""), ("model_name",)),
    ("02_long_model_version", _set("model_version", "v" * 51), ("model_version",)),
    ("03_missing_result_media", _drop("result_video_media_id"), ("result_video_media_id",)),
    ("04_overall_score_above_100", _set("overall_score", 100.01), ("overall_score",)),
    ("05_negative_correct_form_pct", _set("correct_form_pct", -1), ("correct_form_pct",)),
    ("06_long_feedback_summary", _set("feedback_summary", "x" * 2001), ("feedback_summary",)),
    ("07_rep_no_gap", _set_rep_numbers([1, 3]), None),
    ("08_rep_no_duplicate", _set_rep_numbers([1, 1]), None),
    ("09_negative_eccentric_ms", _set_first_rep(eccentric_ms=-1), ("rep_events", 0, "eccentric_ms")),
    ("10_max_angle_below_min", _set_first_rep(min_joint_angle_deg=120, max_joint_angle_deg=90), None),
    ("11_too_many_reps", _set("rep_events", _valid_reps(1001)), ("rep_events",)),
]


@pytest.mark.tc("SRT-19")
@pytest.mark.parametrize(
    ("mutate", "expected_loc"),
    [(mutate, loc) for _, mutate, loc in RESULT_INVALID_CASES],
    ids=[case_id for case_id, _, _ in RESULT_INVALID_CASES],
)
def test_create_result_request_with_invalid_field_raises_validation_error(
    mutate: Callable[[dict[str, Any]], None], expected_loc: tuple[str | int, ...] | None
) -> None:
    body = res(uuid.uuid4(), REPS3)
    mutate(body)

    with pytest.raises(ValidationError) as exc:
        VideoJobResultRequest(**body)

    if expected_loc is not None:
        assert exc.value.errors()[0]["loc"] == expected_loc


@pytest.mark.tc("SRT-19")
def test_create_result_request_with_rep_no_not_continuous_reports_rep_events() -> None:
    for numbers in ([1, 3], [1, 1]):
        body = res(uuid.uuid4(), REPS3)
        _set_rep_numbers(numbers)(body)

        with pytest.raises(ValidationError) as exc:
            VideoJobResultRequest(**body)

        error = exc.value.errors()[0]
        assert "rep_events" in error["loc"]
        assert "rep_no phải liên tục từ 1 và không trùng" in error["msg"]


@pytest.mark.tc("SRT-19")
@pytest.mark.parametrize("error_message", ["", "x" * 2001], ids=["12_empty", "13_too_long"])
def test_create_failure_request_with_invalid_error_message_raises_validation_error(error_message: str) -> None:
    with pytest.raises(ValidationError) as exc:
        VideoJobFailureRequest(error_message=error_message)

    assert exc.value.errors()[0]["loc"] == ("error_message",)


@pytest.mark.tc("SRT-19")
def test_create_result_request_with_valid_body_succeeds() -> None:
    media = uuid.uuid4()

    with_reps = VideoJobResultRequest(**res(media, REPS3))
    without_reps = VideoJobResultRequest(**res(uuid.uuid4(), []))

    assert len(with_reps.rep_events) == 3
    assert with_reps.result_video_media_id == media
    assert with_reps.overall_score == 85
    assert with_reps.correct_form_pct == 90
    assert with_reps.rep_events[1].min_joint_angle_deg is None
    assert with_reps.rep_events[2].is_full_rom is False
    assert len(without_reps.rep_events) == 0


@pytest.mark.tc("SRT-19")
def test_create_result_request_without_optional_fields_defaults_to_none() -> None:
    body = res(uuid.uuid4(), REPS3)
    for field in ("overall_score", "correct_form_pct", "feedback_summary", "rep_events"):
        del body[field]

    req = VideoJobResultRequest(**body)

    assert req.overall_score is None
    assert req.correct_form_pct is None
    assert req.feedback_summary is None
    assert req.rep_events == []


@pytest.mark.tc("SRT-19")
def test_create_failure_request_with_valid_message_succeeds() -> None:
    req = VideoJobFailureRequest(error_message="Không giải mã được video H.265")

    assert req.error_message == "Không giải mã được video H.265"


@pytest.mark.parametrize(
    ("body", "expected_loc"),
    [
        ({"set_id": 0, "source_video_media_id": str(uuid.uuid4())}, ("set_id",)),
        ({"set_id": 9223372036854775808, "source_video_media_id": str(uuid.uuid4())}, ("set_id",)),
        ({"set_id": 1, "source_video_media_id": "khong-phai-uuid"}, ("source_video_media_id",)),
    ],
    ids=["zero_set_id", "set_id_over_bigint", "bad_uuid"],
)
def test_create_video_job_request_with_invalid_field_raises_validation_error(
    body: dict[str, Any], expected_loc: tuple[str, ...]
) -> None:
    with pytest.raises(ValidationError) as exc:
        CreateVideoJobRequest(**body)

    assert exc.value.errors()[0]["loc"] == expected_loc


def test_create_video_job_request_with_valid_body_succeeds() -> None:
    media = uuid.uuid4()

    req = CreateVideoJobRequest(set_id=9223372036854775807, source_video_media_id=media)

    assert req.model_dump() == {"set_id": 9223372036854775807, "source_video_media_id": media}
