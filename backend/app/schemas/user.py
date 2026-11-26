"""Schema Pydantic cho /users (quản trị người dùng, doc 04 §4.10; spec auth-users quyết định 8)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import RoleCode, UnitSystem, UserStatus


class UpdateUserRolesRequest(BaseModel):
    """
    Body `PUT /users/{user_id}/roles`: tập role mới thay thế toàn bộ tập cũ (doc 04 §4.10).
    Không rỗng, bắt buộc có `user`, mã trùng được bỏ (giữ thứ tự xuất hiện đầu tiên).
    """

    roles: list[RoleCode] = Field(
        ...,
        min_length=1,
        description="Mã role (`user`, `content_editor`, `admin`); bắt buộc có `user`",
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"roles": ["user", "content_editor"]}},
    )

    @field_validator("roles")
    @classmethod
    def _require_user_role(cls, roles: list[RoleCode]) -> list[RoleCode]:
        # field_validator (không phải model_validator) để lỗi gắn `field="roles"`.
        if RoleCode.USER not in roles:
            raise ValueError("Tập role phải luôn có `user`")
        return list(dict.fromkeys(roles))


class UserAdminOut(BaseModel):
    """
    Người dùng nhìn từ phía quản trị: tài khoản (`auth.users`) + hồ sơ (`auth.user_profiles`) + role còn hiệu lực.
    Field hồ sơ là null nếu user chưa có `user_profiles`. Không trả `password_hash`, `phone_number`.
    """

    id: uuid.UUID
    email: str
    status: UserStatus
    email_verified_at: datetime | None
    locked_until: datetime | None
    display_name: str | None
    full_name: str | None
    locale: str | None
    timezone: str | None
    unit_system: UnitSystem | None
    roles: list[str] = Field(
        ..., description="Mã role còn hiệu lực (bỏ role hết hạn), sắp xếp tăng dần"
    )
    created_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "5eed0000-0000-4000-8000-000000000003",
                "email": "demo@smartworkout.local",
                "status": "active",
                "email_verified_at": "2026-09-28T08:40:00Z",
                "locked_until": None,
                "display_name": "An",
                "full_name": "Nguyễn Văn An",
                "locale": "vi-VN",
                "timezone": "Asia/Ho_Chi_Minh",
                "unit_system": "metric",
                "roles": ["user"],
                "created_at": "2026-09-28T08:30:00Z",
            }
        }
    )
