"""
Smart Workout AI - FastAPI Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# from app.core.config import settings
# from app.api.v1.router import api_v1_router

app = FastAPI(
    title="Smart Workout AI",
    description="API cho ứng dụng quản lý tập luyện thể hình tích hợp AI",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
# app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": "Smart Workout AI",
        "version": "0.1.0",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "services": {
            "database": "connected",  # TODO: actual check
            "redis": "connected",     # TODO: actual check
            "ai_service": "ready",    # TODO: actual check
        },
    }
