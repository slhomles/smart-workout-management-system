"""Unit test phần core không cần DB: cấu hình, token, cursor, Page, Alembic baseline."""

import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from jose import jwt
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.exceptions import DataValidationError
from app.core.security import create_access_token, generate_refresh_token, hash_token, verify_password
from app.schemas.base import Page, Pagination, decode_cursor, encode_cursor

BACKEND = Path(__file__).resolve().parents[2]


def test_settings_reject_unsafe_production_values():
    with pytest.raises(ValidationError):
        Settings(APP_ENV="production", CORS_ORIGINS=["http://app.local"], _env_file=None)
    with pytest.raises(ValidationError):
        Settings(APP_ENV="production", JWT_SECRET_KEY="x" * 40, CORS_ORIGINS=["*"], _env_file=None)
    ok = Settings(APP_ENV="production", JWT_SECRET_KEY="x" * 40, CORS_ORIGINS=["http://app.local"], _env_file=None)
    assert ok.CORS_ORIGINS == ["http://app.local"]


def test_settings_parse_cors_json_and_cache(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:8081"]')
    assert Settings(_env_file=None).CORS_ORIGINS == ["http://localhost:8081"]
    assert get_settings() is get_settings()


def test_access_token_claims():
    user_id, device_id = uuid.uuid4(), uuid.uuid4()
    token = create_access_token(user_id=user_id, roles=["user"], device_id=device_id)
    settings = get_settings()
    claims = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert set(claims) == {"sub", "roles", "did", "type", "iat", "exp", "jti"}
    assert claims["sub"] == str(user_id) and claims["did"] == str(device_id) and claims["type"] == "access"
    assert claims["exp"] - claims["iat"] == settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60


def test_refresh_token_and_password_helpers():
    raw, digest = generate_refresh_token()
    assert len(raw) >= 43 and hash_token(raw) == digest and len(digest) == 64
    assert hash_token("seed-refresh-demo-2") == hash_token("seed-refresh-demo-2")
    assert verify_password("anything", None) is False


def test_cursor_round_trip_and_page_shape():
    value = {"id": "5eed0000-0000-4000-8000-000000000003"}
    cursor = encode_cursor(value)
    assert decode_cursor(cursor) == value and "=" not in cursor
    page = Page[int](data=[], pagination=Pagination(next_cursor=None, has_more=False))
    assert page.model_dump() == {"data": [], "pagination": {"next_cursor": None, "has_more": False}}


def test_decode_cursor_rejects_garbage():
    with pytest.raises(DataValidationError) as caught:
        decode_cursor("!!!khong-phai-cursor")
    assert caught.value.status_code == 422 and caught.value.details[0].field == "cursor"


def test_alembic_has_single_empty_baseline():
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0001_baseline"]
    baseline = script.get_revision("0001_baseline")
    assert baseline.down_revision is None
    source = Path(baseline.path).read_text(encoding="utf-8")
    assert "op." not in source
    env = (BACKEND / "alembic" / "env.py").read_text(encoding="utf-8")
    assert "include_schemas=True" in env and "target_metadata = Base.metadata" in env
