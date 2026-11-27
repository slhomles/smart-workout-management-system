"""Unit test client AI dự đoán phục hồi (spec workout-routine WRT-22), không DB, không mạng thật."""

import json
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

import httpx
import pytest

from app.core.config import get_settings
from app.schemas.recovery import MuscleLoadSchema, RecoveryPredictionInput
from app.services.recovery_ai_client import RecoveryServiceError, predict_recovery

VALID_BODY = {
    "model_version": "recovery-v1",
    "predictions": [{"muscle_group_id": 1, "fatigue_score": 72.5, "recovered_at": "2026-11-29T10:00:00Z"}],
}
Handler = Callable[[httpx.Request], httpx.Response]


def _payload() -> RecoveryPredictionInput:
    return RecoveryPredictionInput(
        session_id=uuid.uuid4(),
        user_id=uuid.UUID("5eed0000-0000-4000-8000-000000000003"),
        trained_at=datetime(2026, 11, 27, 1, 0, tzinfo=timezone.utc),
        muscle_loads=[
            MuscleLoadSchema(
                muscle_group_id=1, direct_sets=3, effective_sets=3.0, total_reps=24, weighted_volume_kg=1440.0,
                avg_rpe=None, base_recovery_hours=60,
            )
        ],
    )


async def _call(handler: Handler):
    return await predict_recovery(_payload(), transport=httpx.MockTransport(handler))


@pytest.mark.tc("WRT-22")
async def test_predict_recovery_valid_response_returns_parsed_output():
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json=VALID_BODY)

    result = await _call(handler)
    assert result.model_version == "recovery-v1"
    assert len(result.predictions) == 1
    prediction = result.predictions[0]
    assert (prediction.muscle_group_id, prediction.fatigue_score) == (1, 72.5)
    assert prediction.recovered_at == datetime(2026, 11, 29, 10, 0, tzinfo=timezone.utc)
    assert prediction.recovered_at.tzinfo is not None
    assert len(sent) == 1
    request = sent[0]
    assert request.method == "POST"
    assert str(request.url) == get_settings().AI_SERVICE_URL.rstrip("/") + "/recovery/predict"
    assert set(json.loads(request.content)) == {"session_id", "user_id", "trained_at", "muscle_loads"}


@pytest.mark.tc("WRT-22")
async def test_predict_recovery_connect_error_raises_down():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("x", request=request)

    with pytest.raises(RecoveryServiceError) as caught:
        await _call(handler)
    assert caught.value.reason == "down"


@pytest.mark.tc("WRT-22")
async def test_predict_recovery_server_error_raises_down():
    with pytest.raises(RecoveryServiceError) as caught:
        await _call(lambda request: httpx.Response(500, json={"detail": "boom"}))
    assert caught.value.reason == "down"


def _with_fatigue(score: float) -> dict:
    prediction = {**VALID_BODY["predictions"][0], "fatigue_score": score}
    return {**VALID_BODY, "predictions": [prediction]}


@pytest.mark.tc("WRT-22")
@pytest.mark.parametrize(
    "make_response",
    [
        lambda request: httpx.Response(200, json=_with_fatigue(150)),
        lambda request: httpx.Response(200, content=b"khong-phai-json"),
        lambda request: httpx.Response(200, json="khong-phai-json"),
        lambda request: httpx.Response(200, json={"predictions": VALID_BODY["predictions"]}),
    ],
    ids=["fatigue_out_of_range", "raw_text_body", "json_string_body", "missing_model_version"],
)
async def test_predict_recovery_contract_violation_raises_invalid_response(make_response: Handler):
    with pytest.raises(RecoveryServiceError) as caught:
        await _call(make_response)
    assert caught.value.reason == "invalid_response"
