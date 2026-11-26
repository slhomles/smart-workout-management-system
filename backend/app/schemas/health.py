"""Schema Pydantic cho GET /api/v1/health (doc 05 §7.6)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    database: Literal["up"]
    redis: Literal["up"]
    ai_service: Literal["up", "degraded"]
    checked_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "database": "up",
                "redis": "up",
                "ai_service": "degraded",
                "checked_at": "2026-11-26T03:20:41Z",
            }
        }
    )
