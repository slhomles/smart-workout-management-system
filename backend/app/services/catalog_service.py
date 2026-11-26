"""Nghiệp vụ module Catalog/Wiki (chức năng 1): tìm bài tập, cây nhóm cơ, danh sách thiết bị.

Module chỉ đọc DB nên không có ranh giới transaction/commit.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DataValidationError
from app.crud import catalog as crud
from app.schemas.base import ErrorDetail, Page, Pagination, build_page, decode_cursor
from app.schemas.catalog import (
    BodyRegionSchema,
    EquipmentCategorySchema,
    EquipmentQuery,
    EquipmentResponse,
    ExerciseSearchQuery,
    ExerciseSummaryResponse,
    MuscleGroupResponse,
)

_INT4_MAX = 2147483647


def _int_from_cursor(cursor: str, key: str) -> int:
    """Đọc số nguyên 0..2^31-1 ở `key` của cursor; sai kiểu/khoảng → 422 `validation_error` field `cursor`."""
    value = decode_cursor(cursor).get(key)
    # bool là lớp con của int trong Python: {"id": true} không phải vị trí hợp lệ.
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= _INT4_MAX:
        raise DataValidationError([ErrorDetail(field="cursor", message="Cursor không hợp lệ", code="invalid_cursor")])
    return value


# --- Bài tập ---
def _search_filter(query: ExerciseSearchQuery) -> crud.ExerciseSearchFilter:
    # Với hàm SQL, mảng rỗng nghĩa là "không có thiết bị/nhóm cơ nào" còn NULL là "không lọc";
    # client không gửi param nào thì phải là không lọc.
    keyword = query.q.strip() if query.q is not None else ""
    return crud.ExerciseSearchFilter(
        keyword=keyword or None,
        muscle_group_ids=query.muscle_group_id or None,
        is_primary_only=query.is_primary_only,
        available_equipment_ids=query.available_equipment_id or None,
        max_difficulty_rank=query.max_difficulty_rank,
    )


def _exercise_summary(row: Any) -> ExerciseSummaryResponse:
    # Cột của crud đã đặt alias trùng tên field response.
    return ExerciseSummaryResponse.model_validate(dict(row))


async def search_exercises(db: AsyncSession, query: ExerciseSearchQuery) -> Page[ExerciseSummaryResponse]:
    """Tìm & lọc bài tập đã xuất bản; cursor `{"offset": n}` vì hàm SQL chỉ hỗ trợ LIMIT/OFFSET."""
    offset = _int_from_cursor(query.cursor, "offset") if query.cursor is not None else 0
    rows = await crud.search_exercises(db, _search_filter(query), limit=query.limit + 1, offset=offset)
    return build_page(rows, query.limit, _exercise_summary, lambda _row: {"offset": offset + query.limit})


# --- Nhóm cơ ---
def _muscle_group_node(row: Any, children: list[MuscleGroupResponse]) -> MuscleGroupResponse:
    body_region = None
    if row["body_region_id"] is not None:
        body_region = BodyRegionSchema(
            id=row["body_region_id"], code=row["body_region_code"], name=row["body_region_name"]
        )
    return MuscleGroupResponse(
        id=row["id"],
        code=row["code"],
        name=row["name"],
        name_en=row["name_en"],
        parent_id=row["parent_id"],
        body_region=body_region,
        heatmap_region_key=row["heatmap_region_key"],
        base_recovery_hours=row["base_recovery_hours"],
        display_order=row["display_order"],
        description=row["description"],
        children=children,
    )


def _subtree(parent_id: int | None, rows_by_parent: dict[int | None, list[Any]]) -> list[MuscleGroupResponse]:
    # Đi xuống từ nút gốc nên dựng được nhiều cấp; thứ tự con giữ nguyên thứ tự đã sắp ở crud.
    return [
        _muscle_group_node(row, _subtree(row["id"], rows_by_parent))
        for row in rows_by_parent.get(parent_id, [])
    ]


async def list_muscle_groups(db: AsyncSession) -> Page[MuscleGroupResponse]:
    """Cây nhóm cơ trong một trang duy nhất (danh mục giải phẫu cố định, không phân trang)."""
    rows_by_parent: dict[int | None, list[Any]] = {}
    for row in await crud.list_muscle_groups(db):
        rows_by_parent.setdefault(row["parent_id"], []).append(row)
    return Page(data=_subtree(None, rows_by_parent), pagination=Pagination(next_cursor=None, has_more=False))


# --- Thiết bị ---
def _equipment_item(row: Any) -> EquipmentResponse:
    return EquipmentResponse(
        id=row["id"],
        code=row["code"],
        name=row["name"],
        name_en=row["name_en"],
        description=row["description"],
        category=EquipmentCategorySchema(id=row["category_id"], code=row["category_code"], name=row["category_name"]),
        image_media_id=row["image_media_id"],
        synonyms=list(row["synonyms"]),
    )


async def list_equipment(db: AsyncSession, query: EquipmentQuery) -> Page[EquipmentResponse]:
    """Thiết bị chưa xoá mềm, keyset `id ASC`; cursor `{"id": <id cuối trang>}`."""
    after_id = _int_from_cursor(query.cursor, "id") if query.cursor is not None else None
    rows = await crud.list_equipment(db, category_id=query.category_id, after_id=after_id, limit=query.limit + 1)
    return build_page(rows, query.limit, _equipment_item, lambda row: {"id": row["id"]})
