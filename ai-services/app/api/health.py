"""`GET /health` (06-ai-contracts.md §2.2): 200 khi mọi model bắt buộc đã sẵn sàng, ngược lại 503."""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.contracts import HealthResponse
from app.core.errors import ServiceUnavailableError
from app.core.models import registry

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    if not registry.is_ready():
        raise ServiceUnavailableError("Model AI chưa sẵn sàng")
    return HealthResponse(status="ok", models=registry.versions(), checked_at=datetime.now(timezone.utc))
