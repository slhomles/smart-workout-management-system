"""
API v1 Router - Tổng hợp tất cả routers.
Mỗi module chỉ thêm đúng 1 dòng include_router, theo thứ tự bảng chữ cái (doc 05 §9.4).
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    body,
    catalog,
    dashboard,
    gallery,
    health,
    reports,
    users,
    workout_routine,
    workout_sessions,
)

api_v1_router = APIRouter()

api_v1_router.include_router(auth.router)
api_v1_router.include_router(body.router)
api_v1_router.include_router(catalog.router)
api_v1_router.include_router(dashboard.router)
api_v1_router.include_router(gallery.router)
api_v1_router.include_router(health.router)
api_v1_router.include_router(reports.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(workout_routine.router)
api_v1_router.include_router(workout_sessions.router)
