"""Fixture chung cho test AI service: client gọi app trong process, không cần GPU hay trọng số model."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.models import registry
from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_registry() -> Iterator[None]:
    """Mỗi test bắt đầu với sổ đăng ký model trống, để test không phụ thuộc thứ tự chạy."""
    saved = dict(registry.models)
    registry.models.clear()
    yield
    registry.models.clear()
    registry.models.update(saved)
