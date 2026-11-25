"""Schema Pydantic cho /auth (doc 04 §4)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DevicePlatform, UnitSystem, UserStatus


class DeviceInfoSchema(BaseModel):
    device_id: uuid.UUID | None = Field(None, description="device_id đã lưu từ lần đăng nhập trước (nếu có)")
    platform: DevicePlatform
    device_name: str | None = Field(None, max_length=100)
    os_version: str | None = Field(None, max_length=30)
    app_version: str | None = Field(None, max_length=30)
    push_token: str | None = Field(None, max_length=512)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)
    device: DeviceInfoSchema

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "demo@smartworkout.local",
                "password": "Demo@123",
                "device": {
                    "device_id": None,
                    "platform": "android",
                    "device_name": "Pixel 8",
                    "os_version": "14",
                    "app_version": "0.1.0",
                    "push_token": None,
                },
            }
        }
    )


class AuthUserSchema(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    roles: list[str]


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Số giây access token còn hiệu lực")
    device_id: uuid.UUID


class LoginResponse(TokenPairResponse):
    user: AuthUserSchema


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1, max_length=512)

    model_config = ConfigDict(json_schema_extra={"example": {"refresh_token": "seed-refresh-demo-2"}})


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1, max_length=512)


class LogoutResponse(BaseModel):
    is_revoked: bool = Field(..., description="TRUE nếu token được thu hồi ở lần gọi này")


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    status: UserStatus
    email_verified_at: datetime | None
    display_name: str | None
    full_name: str | None
    avatar_media_id: uuid.UUID | None
    locale: str | None
    timezone: str | None
    unit_system: UnitSystem | None
    roles: list[str]
    permissions: list[str]
