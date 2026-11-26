"""
Smart Workout AI - FastAPI Application Entry Point
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import ServiceUnavailableError, register_exception_handlers
from app.middleware.logging import RequestContextMiddleware

settings = get_settings()

logging.basicConfig(level=logging.INFO, format="%(message)s")

app = FastAPI(
    title="Smart Workout AI",
    description="API cho ứng dụng quản lý tập luyện thể hình tích hợp AI",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials="*" not in settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Location", "Retry-After"],
)
app.add_middleware(RequestContextMiddleware)

register_exception_handlers(app)

app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/health", tags=["Health"], summary="Kiểm tra tình trạng dịch vụ")
async def health_check() -> dict:
    """
    Kiểm tra PostgreSQL thật (`SELECT 1`); lỗi → 503 service_unavailable.
    TODO(core): thêm Redis PING và AI service (degraded) theo doc 05 §7.6 khi hạ tầng sẵn sàng.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        raise ServiceUnavailableError("Không kết nối được cơ sở dữ liệu") from None
    return {"status": "healthy", "app": settings.APP_NAME, "version": "0.1.0", "services": {"database": "up"}}
