"""
API v1 Router - Tổng hợp tất cả routers.
"""

from fastapi import APIRouter

# from app.api.v1 import auth, users, exercises, workouts, body_metrics, nutrition, progress_gallery, ai_analysis

api_v1_router = APIRouter()

# TODO: Uncomment khi implement từng module
# api_v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
# api_v1_router.include_router(users.router, prefix="/users", tags=["Users"])
# api_v1_router.include_router(exercises.router, prefix="/exercises", tags=["Exercise Wiki"])
# api_v1_router.include_router(workouts.router, prefix="/workouts", tags=["Workout Routines"])
# api_v1_router.include_router(body_metrics.router, prefix="/body-metrics", tags=["Body Metrics"])
# api_v1_router.include_router(nutrition.router, prefix="/nutrition", tags=["Nutrition"])
# api_v1_router.include_router(progress_gallery.router, prefix="/progress-gallery", tags=["Progress Gallery"])
# api_v1_router.include_router(ai_analysis.router, prefix="/ai", tags=["AI Analysis"])
