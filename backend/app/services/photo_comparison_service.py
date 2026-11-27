"""
Nghiệp vụ so sánh Before/After của Progress Gallery (chức năng 4, bước 5): lưu và xem lại cặp ảnh.

Chủ sở hữu cặp suy ra từ hai ảnh (bảng media.photo_comparisons không có user_id); thẻ ảnh đọc từ view
media.v_progress_photo_cards, view này đã lọc ảnh xoá mềm.
"""

import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, DataValidationError
from app.crud import gallery as crud
from app.schemas.base import ErrorDetail, Page, build_page, decode_keyset_cursor
from app.schemas.gallery import CreatePhotoComparisonRequest, ListPhotoComparisonsQuery, PhotoComparisonResponse

# Cùng một thông điệp cho ảnh không tồn tại, đã xoá hay của người khác: không lộ sự tồn tại (doc 05 §2.6).
PHOTO_UNAVAILABLE_MESSAGE = "Không tìm thấy ảnh tiến độ của bạn"

_CardsById = Mapping[uuid.UUID, dict[str, Any]]


def _invalid(field: str, message: str) -> DataValidationError:
    return DataValidationError([ErrorDetail(field=field, message=message, code="value_error")])


async def _cards_by_id(db: AsyncSession, user_id: uuid.UUID, photo_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, Any]]:
    cards = await crud.get_photo_cards(db, user_id, photo_ids)
    return {card["id"]: card for card in cards}


def _owned_card(cards: _CardsById, photo_id: uuid.UUID, field: str) -> dict[str, Any]:
    card = cards.get(photo_id)
    if card is None:
        raise _invalid(field, PHOTO_UNAVAILABLE_MESSAGE)
    return card


async def _validated_pair(
    db: AsyncSession, user_id: uuid.UUID, body: CreatePhotoComparisonRequest
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Kiểm tra theo thứ tự đã chốt (spec §6 ý 8): khác nhau → thuộc user → Before chụp trước After."""
    if body.before_photo_id == body.after_photo_id:
        raise _invalid("after_photo_id", "Ảnh After phải khác ảnh Before")
    cards = await _cards_by_id(db, user_id, [body.before_photo_id, body.after_photo_id])
    before = _owned_card(cards, body.before_photo_id, "before_photo_id")
    after = _owned_card(cards, body.after_photo_id, "after_photo_id")
    if before["taken_at"] >= after["taken_at"]:
        raise _invalid("after_photo_id", "Ảnh After phải được chụp sau ảnh Before")
    return before, after


def _to_response(row: Mapping[str, Any], cards: _CardsById) -> PhotoComparisonResponse:
    return PhotoComparisonResponse.model_validate(
        {
            "id": row["id"],
            "title": row["title"],
            "before": cards[row["before_photo_id"]],
            "after": cards[row["after_photo_id"]],
            "created_at": row["created_at"],
        }
    )


async def create_comparison(
    db: AsyncSession, user_id: uuid.UUID, body: CreatePhotoComparisonRequest
) -> PhotoComparisonResponse:
    """Lưu cặp Before/After của chính user rồi commit; trả cặp kèm đủ thông số hai ảnh."""
    before, after = await _validated_pair(db, user_id, body)
    if await crud.comparison_exists(db, body.before_photo_id, body.after_photo_id):
        raise ConflictError("conflict", "Cặp ảnh này đã được lưu để so sánh")
    comparison = await crud.add_comparison(db, body.before_photo_id, body.after_photo_id, body.title)
    row = {
        "id": comparison.id,
        "title": comparison.title,
        "before_photo_id": comparison.before_photo_id,
        "after_photo_id": comparison.after_photo_id,
        "created_at": comparison.created_at,
    }
    await db.commit()
    return _to_response(row, {before["id"]: before, after["id"]: after})


async def list_comparisons(
    db: AsyncSession, user_id: uuid.UUID, query: ListPhotoComparisonsQuery
) -> Page[PhotoComparisonResponse]:
    """Các cặp so sánh của user, mới tạo trước (keyset `created_at DESC, id DESC`)."""
    # Lấy thêm 1 dòng để biết còn trang sau mà không COUNT(*) (Claude_api_respone §5).
    window = crud.KeysetWindow(after=decode_keyset_cursor(query.cursor, "created_at"), limit=query.limit + 1)
    rows = await crud.list_comparisons(db, user_id, window)
    photo_ids = list({photo_id for r in rows for photo_id in (r["before_photo_id"], r["after_photo_id"])})
    cards = await _cards_by_id(db, user_id, photo_ids) if photo_ids else {}
    return build_page(
        rows,
        query.limit,
        to_item=lambda r: _to_response(r, cards),
        cursor_of=lambda r: {"created_at": r["created_at"].isoformat(), "id": str(r["id"])},
    )
