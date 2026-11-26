"""
Kiểm tra tình trạng phụ thuộc thật (doc 05 §7.6):
- PostgreSQL (`SELECT 1`) và Redis (`PING`) hỏng → 503 service_unavailable.
- AI service (`GET {AI_SERVICE_URL}/health`) hỏng chỉ đánh dấu `degraded` (backend vẫn phục vụ được).
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ServiceUnavailableError
from app.core.redis_client import get_redis
from app.schemas.base import ErrorDetail
from app.schemas.health import HealthResponse

logger = logging.getLogger("app.health")


async def _check_database(db: AsyncSession) -> bool:
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.warning("health: database down", exc_info=True)
        return False


async def _check_redis() -> bool:
    try:
        return bool(await get_redis().ping())
    except Exception:
        logger.warning("health: redis down", exc_info=True)
        return False


async def _check_ai_service() -> bool:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=settings.AI_HEALTH_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{settings.AI_SERVICE_URL.rstrip('/')}/health")
        return response.status_code == 200
    except Exception:
        logger.info("health: ai service unreachable")
        return False


async def check_health(db: AsyncSession) -> HealthResponse:
    database_ok = await _check_database(db)
    redis_ok, ai_ok = await asyncio.gather(_check_redis(), _check_ai_service())

    down = [name for name, ok in (("database", database_ok), ("redis", redis_ok)) if not ok]
    if down:
        raise ServiceUnavailableError(
            "Một phụ thuộc bắt buộc đang không khả dụng",
            [ErrorDetail(field=name, message=f"{name} không kết nối được", code="down") for name in down],
        )
    return HealthResponse(
        database="up",
        redis="up",
        ai_service="up" if ai_ok else "degraded",
        checked_at=datetime.now(timezone.utc),
    )
