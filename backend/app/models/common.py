"""Kiểu cột dùng chung cho model SQLAlchemy."""

from enum import Enum

from sqlalchemy.dialects.postgresql import ENUM


def pg_enum(enum_cls: type[Enum], name: str, schema: str) -> ENUM:
    """Ánh xạ tới kiểu ENUM đã có trong DB (không tạo kiểu mới), lưu bằng `.value`."""
    return ENUM(
        enum_cls,
        name=name,
        schema=schema,
        create_type=False,
        values_callable=lambda e: [m.value for m in e],
    )
