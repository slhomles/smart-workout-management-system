"""Unit test không cần DB cho worker video: cấu hình AI_WORKER_TOKEN và dependency verify_worker_token (06 §3.1)."""

import hmac

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.dependencies import verify_worker_token
from app.core.exceptions import UnauthorizedError

WT = "wt-test-" + "a" * 40
PRODUCTION = dict(APP_ENV="production", JWT_SECRET_KEY="x" * 40, CORS_ORIGINS=["http://app.local"], _env_file=None)


@pytest.mark.tc("VWK-15")
@pytest.mark.parametrize("override", [{}, {"AI_WORKER_TOKEN": ""}, {"AI_WORKER_TOKEN": "k" * 31}])
def test_settings_production_weak_worker_token_rejected(monkeypatch, override):
    monkeypatch.delenv("AI_WORKER_TOKEN", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        Settings(**PRODUCTION, **override)
    assert isinstance(exc_info.value, ValueError)
    assert "AI_WORKER_TOKEN" in str(exc_info.value)


@pytest.mark.tc("VWK-15")
def test_settings_valid_or_development_worker_token_accepted(monkeypatch):
    monkeypatch.delenv("AI_WORKER_TOKEN", raising=False)
    production = Settings(**PRODUCTION, AI_WORKER_TOKEN="k" * 32)
    assert production.AI_WORKER_TOKEN == "k" * 32
    development = Settings(_env_file=None)
    assert development.APP_ENV == "development"
    assert development.AI_WORKER_TOKEN == ""


async def test_verify_worker_token_matching_header_returns_none(monkeypatch):
    monkeypatch.setattr(get_settings(), "AI_WORKER_TOKEN", WT)
    assert await verify_worker_token(WT) is None


@pytest.mark.parametrize("header", [None, "", "sai-token-" + "a" * 40, WT[:-1], "tôken"])
async def test_verify_worker_token_missing_or_wrong_header_raises_unauthorized(monkeypatch, header):
    monkeypatch.setattr(get_settings(), "AI_WORKER_TOKEN", WT)
    with pytest.raises(UnauthorizedError) as exc_info:
        await verify_worker_token(header)
    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "unauthorized"


@pytest.mark.parametrize("header", [None, "", WT])
async def test_verify_worker_token_empty_configured_token_raises_unauthorized(monkeypatch, header):
    monkeypatch.setattr(get_settings(), "AI_WORKER_TOKEN", "")
    with pytest.raises(UnauthorizedError) as exc_info:
        await verify_worker_token(header)
    assert exc_info.value.code == "unauthorized"


async def test_verify_worker_token_compares_bytes_via_hmac(monkeypatch):
    calls: list[tuple[object, object]] = []
    original = hmac.compare_digest

    def spy(a, b):
        calls.append((a, b))
        return original(a, b)

    monkeypatch.setattr(hmac, "compare_digest", spy)
    monkeypatch.setattr(get_settings(), "AI_WORKER_TOKEN", WT)
    await verify_worker_token(WT)
    with pytest.raises(UnauthorizedError):
        await verify_worker_token("tôken")
    assert len(calls) == 2
    assert all(isinstance(a, bytes) and isinstance(b, bytes) for a, b in calls)
