"""Cấu hình AI service, đọc từ biến môi trường hoặc `ai-services/.env` (không commit)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "SmartWorkoutAI-AIServices"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Thư mục trọng số model (không commit, docs/architecture/06-ai-contracts.md §2.4).
    MODELS_DIR: Path = SERVICE_ROOT / "models"

    # Worker video gọi backend (06-ai-contracts.md §3).
    BACKEND_URL: str = "http://localhost:8000"
    AI_WORKER_TOKEN: str = ""
    AI_WORKER_POLL_SECONDS: float = 5.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
