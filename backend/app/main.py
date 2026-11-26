"""
Smart Workout AI - FastAPI Application Entry Point
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import register_exception_handlers
from app.core.redis_client import close_redis
from app.middleware.logging import RequestContextMiddleware

logging.basicConfig(level=logging.INFO, format="%(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await close_redis()
    await engine.dispose()


def create_app() -> FastAPI:
    """App factory: test dựng app riêng rồi gắn thêm route thử nghiệm mà không đụng app thật."""
    settings = get_settings()
    application = FastAPI(
        title="Smart Workout AI",
        description="API cho ứng dụng quản lý tập luyện thể hình tích hợp AI",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials="*" not in settings.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Location", "Retry-After"],
    )
    application.add_middleware(RequestContextMiddleware)
    register_exception_handlers(application)
    application.include_router(api_v1_router, prefix="/api/v1")
    return application


app = create_app()
