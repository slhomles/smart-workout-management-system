"""Unit test sinh presigned GET URL của S3 (spec be-media-delivery MED-10): boto3 thật, khoá giả, không DB, không mạng."""

import inspect

import pytest

from app.core.config import get_settings
from app.services import storage_service

BUCKET = "smart-workout-media"
OBJECT_KEY = "catalog/exercises/dumbbell-row/demo.gif"
FAKE_ACCESS_KEY = "test-access-key"


@pytest.fixture
def fake_aws_credentials(monkeypatch):
    # backend/.env có thể chứa khoá AWS thật: thay bằng khoá giả để việc ký chỉ chạy cục bộ.
    settings = get_settings()
    monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", FAKE_ACCESS_KEY)
    monkeypatch.setattr(settings, "AWS_SECRET_ACCESS_KEY", "test-secret-key")
    monkeypatch.setattr(settings, "AWS_S3_REGION", "ap-southeast-1")


@pytest.mark.tc("MED-10")
async def test_presign_get_url_fake_credentials_returns_signed_https_url(fake_aws_credentials):
    presign_get_url = storage_service.presign_get_url
    assert inspect.iscoroutinefunction(presign_get_url) is True

    url = await presign_get_url(BUCKET, OBJECT_KEY, 900)

    assert isinstance(url, str)
    assert url.startswith("https://")
    assert BUCKET in url
    assert OBJECT_KEY in url
    assert "Signature" in url
    # Chứng minh URL được ký bằng khoá giả của test, không phải khoá đọc từ .env.
    assert FAKE_ACCESS_KEY in url
