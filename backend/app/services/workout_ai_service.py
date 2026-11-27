"""
Service Training dành cho module AI (chức năng 6, luồng video 1B).

Module AI không import crud/model của Training (doc 05 §6.3); mọi đọc/ghi hiệp tập đi qua đây.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.crud import workout as crud

# Một message cho mọi lý do (không tồn tại / của user khác / buổi xoá mềm) để không lộ dữ liệu (doc 04 §2.4).
_SET_NOT_FOUND = ("exercise_set_not_found", "Không tìm thấy hiệp tập")


@dataclass(frozen=True)
class OwnedSetContext:
    """Ngữ cảnh một hiệp thuộc user: buổi, bài trong buổi và bài tập."""

    set_id: int
    session_exercise_id: uuid.UUID
    session_id: uuid.UUID
    exercise_id: int
    exercise_name: str
    supports_ai_tracking: bool


async def get_owned_set_context(db: AsyncSession, user_id: uuid.UUID, set_id: int) -> OwnedSetContext:
    """Lấy ngữ cảnh hiệp của user; không có/của user khác/buổi xoá mềm → 404 exercise_set_not_found."""
    row = await crud.owned_set_context(db, user_id, set_id)
    if row is None:
        raise NotFoundError(*_SET_NOT_FOUND)
    return OwnedSetContext(**row)
