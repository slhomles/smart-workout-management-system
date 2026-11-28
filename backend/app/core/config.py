"""
Application configuration using pydantic-settings.
Loads values from environment variables / .env file.

Chỉ lấy cấu hình qua get_settings() (doc 05 §7.3).
"""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "change-this-secret-key"


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "SmartWorkoutAI"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    # JSON list, vd: ["http://localhost:8081"]. "*" chỉ được phép khi APP_ENV=development.
    CORS_ORIGINS: list[str] = ["*"]

    # --- PostgreSQL ---
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "smart_workout"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "smart_workout_db"
    DB_ECHO: bool = False

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # --- MongoDB (chưa dùng, doc 05 §7.2) ---
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "smart_workout_docs"

    # --- Redis ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Cache permission `perm:{user_id}` (doc 04 §2.4); Redis không phải nguồn dữ liệu chính.
    PERMISSION_CACHE_TTL_SECONDS: int = 300
    REDIS_SOCKET_TIMEOUT_SECONDS: float = 2.0
    # --- JWT (doc 04 §3) ---
    JWT_SECRET_KEY: str = DEFAULT_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Auth policy (doc 04 §4.2, §6.2) ---
    REQUIRE_EMAIL_VERIFICATION: bool = False
    LOGIN_MAX_FAILED_ATTEMPTS: int = 5
    LOGIN_FAILURE_WINDOW_MINUTES: int = 15
    LOGIN_LOCK_MINUTES: int = 15

    # --- AWS S3 ---
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET: str = "smart-workout-media"
    AWS_S3_REGION: str = "ap-southeast-1"

    # --- Object Storage ---
    # "local": dev chưa có S3 — ghi file vào LOCAL_STORAGE_DIR/<bucket>/<object_key>, cùng bố cục key với S3.
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    LOCAL_STORAGE_DIR: str = ".storage"
    # Font TrueType có dấu tiếng Việt để vẽ thẻ báo cáo; để trống thì tự dò font hệ thống.
    REPORT_FONT_PATH: str = ""

    # --- AI Services ---
    AI_SERVICE_URL: str = "http://localhost:8001"
    AI_HEALTH_TIMEOUT_SECONDS: float = 2.0
    # Bí mật chung với worker video (header X-Worker-Token, 06-ai-contracts §3.1); rỗng thì mọi request worker bị 401.
    AI_WORKER_TOKEN: str = ""

    @model_validator(mode="after")
    def _check_production_safety(self) -> "Settings":
        """Ngoài development: chặn JWT_SECRET_KEY/AI_WORKER_TOKEN yếu và CORS '*'.

        Căn cứ: doc 04 §6.4, doc 05 §7.3, 06-ai-contracts §3.1.
        """
        if self.APP_ENV != "development":
            if self.JWT_SECRET_KEY == DEFAULT_JWT_SECRET or len(self.JWT_SECRET_KEY) < 32:
                raise ValueError("JWT_SECRET_KEY phải là chuỗi ngẫu nhiên ≥ 32 ký tự ngoài môi trường development")
            if "*" in self.CORS_ORIGINS:
                raise ValueError("CORS_ORIGINS không được chứa '*' ngoài môi trường development")
            if len(self.AI_WORKER_TOKEN) < 32:
                raise ValueError("AI_WORKER_TOKEN phải là chuỗi ngẫu nhiên ≥ 32 ký tự ngoài môi trường development")
        return self


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
