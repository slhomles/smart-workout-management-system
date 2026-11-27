"""
Service Training dành cho module AI (chức năng 6, luồng video 1B).

Module AI không import crud/model của Training (doc 05 §6.3); mọi đọc/ghi hiệp tập đi qua đây.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.crud import workout as crud
from app.models.enums import LogSource
from app.models.training import SetRepEvent
from app.schemas.workout import RepEventInput

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


async def apply_ai_rep_events(
    db: AsyncSession, set_id: int, rep_events: list[RepEventInput], source: LogSource
) -> None:
    """Thay toàn bộ rep của hiệp bằng rep AI, đặt `reps = len(rep_events)` và `source`; KHÔNG commit.

    `rep_events` rỗng thì không đổi gì. Hiệp không có → 404 exercise_set_not_found.
    `weight_kg` giữ nguyên vì AI không biết mức tạ. Ghi được cả khi buổi đã kết thúc (gửi video từ lịch sử).
    """
    if not rep_events:
        return
    exercise_set = await crud.lock_set(db, set_id)
    if exercise_set is None:
        raise NotFoundError(*_SET_NOT_FOUND)
    # Xoá trước rồi chèn lại, để rep mới không trùng pk_set_rep_events (set_id, rep_no).
    await crud.delete_rep_events(db, set_id)
    db.add_all([SetRepEvent(set_id=set_id, **event.model_dump()) for event in rep_events])
    exercise_set.reps = len(rep_events)
    exercise_set.source = source
    await db.flush()
