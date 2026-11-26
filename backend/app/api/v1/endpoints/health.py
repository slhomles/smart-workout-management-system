"""Endpoint /health (doc 05 §7.6). Chỉ nhận request, gọi service, trả kết quả."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.base import ErrorResponse
from app.schemas.health import HealthResponse
from app.services import health_service

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    response_model=HealthResponse,
    status_code=200,
    responses={503: {"model": ErrorResponse, "description": "service_unavailable: PostgreSQL hoặc Redis hỏng"}},
    summary="Kiểm tra tình trạng dịch vụ",
    description=(
        "Quyền: **công khai**. Kiểm tra thật PostgreSQL (`SELECT 1`) và Redis (`PING`); hỏng một trong hai → "
        "503 `service_unavailable`. AI service lỗi chỉ trả `ai_service = degraded`."
    ),
)
async def get_health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    return await health_service.check_health(db)
