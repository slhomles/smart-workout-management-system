"""Schema Pydantic cho /auth (doc 04 §4)."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import DevicePlatform, UnitSystem, UserStatus

# Trùng CHECK ck_users_email_format của auth.users (database/postgresql/schemas/02_auth.sql).
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
PASSWORD_MIN_BYTES = 8
PASSWORD_MAX_BYTES = 72  # bcrypt bỏ qua phần sau byte thứ 72 (doc 04 §6.1)


def validate_password_policy(value: str) -> str:
    """
    Chính sách mật khẩu (doc 04 §6.1): 8–72 byte UTF-8, có ít nhất 1 chữ cái và 1 chữ số.
    Dùng chung cho mọi field mật khẩu mới (register, change-password); lỗi → 422 validation_error.
    """
    size = len(value.encode("utf-8"))
    if size < PASSWORD_MIN_BYTES or size > PASSWORD_MAX_BYTES:
        raise ValueError(f"Mật khẩu phải dài từ {PASSWORD_MIN_BYTES} đến {PASSWORD_MAX_BYTES} byte (UTF-8)")
    if not any(ch.isalpha() for ch in value):
        raise ValueError("Mật khẩu phải có ít nhất 1 chữ cái")
    if not any(ch.isdigit() for ch in value):
        raise ValueError("Mật khẩu phải có ít nhất 1 chữ số")
    return value


NewPassword = Annotated[
    str,
    AfterValidator(validate_password_policy),
    Field(description="8–72 byte UTF-8, có ít nhất 1 chữ cái và 1 chữ số"),
]
EmailAddress = Annotated[str, StringConstraints(max_length=254, pattern=EMAIL_PATTERN)]
# varchar(50) + ck_user_profiles_display_name: không rỗng sau khi bỏ khoảng trắng hai đầu; lưu giá trị đã strip.
DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


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


class RevokedTokensResponse(BaseModel):
    """Kết quả `POST /auth/logout-all`: số refresh token bị thu hồi ở lần gọi này."""

    revoked_count: int = Field(..., ge=0, description="Số refresh token chưa thu hồi vừa bị thu hồi")


class ChangePasswordRequest(BaseModel):
    """Body `PATCH /auth/change-password` (doc 04 §4.7). Mật khẩu mới theo chính sách doc 04 §6.1."""

    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: NewPassword

    model_config = ConfigDict(
        json_schema_extra={"example": {"current_password": "Demo@123", "new_password": "Moi@12345"}}
    )


class RegisterRequest(BaseModel):
    """Body `POST /auth/register` (doc 04 §4.2). Không nhận field lạ: client không tự đặt `status`/`roles`."""

    email: EmailAddress
    password: NewPassword
    display_name: DisplayName
    full_name: str | None = Field(None, max_length=100)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "email": "an@example.com",
                "password": "Demo@1234",
                "display_name": "An",
                "full_name": "Nguyễn Văn An",
            }
        },
    )


class RegisterResponse(BaseModel):
    """Tài khoản vừa đăng ký (doc 04 §4.2). Không chứa token, mật khẩu hay `password_hash`."""

    id: uuid.UUID
    email: str
    display_name: str
    full_name: str | None
    roles: list[str]
    status: UserStatus


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
