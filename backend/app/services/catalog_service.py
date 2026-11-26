"""Nghiệp vụ module Catalog/Wiki (chức năng 1): tìm, xem chi tiết, gợi ý bài thay thế, cây nhóm cơ, thiết bị.

Module chỉ đọc DB nên không có ranh giới transaction/commit.
"""

import re
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DataValidationError, NotFoundError
from app.crud import catalog as crud
from app.schemas.base import ErrorDetail, Page, Pagination, build_page, decode_cursor
from app.schemas.catalog import (
    BodyRegionSchema,
    DifficultySchema,
    EquipmentCategorySchema,
    EquipmentExerciseSchema,
    EquipmentQuery,
    EquipmentResponse,
    ExerciseAlternativeResponse,
    ExerciseAlternativesQuery,
    ExerciseDetailResponse,
    ExerciseEquipmentSchema,
    ExerciseInstructionSchema,
    ExerciseMediaSchema,
    ExerciseMistakeSchema,
    ExerciseMuscleSchema,
    ExerciseSearchQuery,
    ExerciseSummaryResponse,
    MuscleGroupResponse,
)

_INT4_MAX = 2147483647
_SchemaT = TypeVar("_SchemaT", bound=BaseModel)
# `[0-9]` thay cho `\d` vì `\d` của Python khớp cả chữ số Unicode; `fullmatch` không nhận "10\n" như `^…$`.
_DIGITS = re.compile(r"[0-9]+")
# Cùng mẫu với ràng buộc `ck_exercises_slug_format` của DB.
_SLUG_FORMAT = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


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


def _exercise_id_in_range(digits: str) -> int | None:
    significant = digits.lstrip("0") or "0"
    # So độ dài trước int(): int() từ chối chuỗi quá 4300 chữ số, và số quá dài chắc chắn tràn `integer`.
    if len(significant) > len(str(_INT4_MAX)):
        return None
    exercise_id = int(significant)
    return exercise_id if exercise_id <= _INT4_MAX else None


async def _get_published_exercise(db: AsyncSession, id_or_slug: str) -> Any:
    """Bài đã xuất bản, chưa xoá mềm theo `id` (chuỗi chữ số) hoặc `slug`; không có → 404 `exercise_not_found`.

    Giá trị ngoài khoảng `integer` hoặc sai định dạng slug chắc chắn không tồn tại nên trả 404 mà không truy vấn:
    truy vấn với giá trị đó làm PostgreSQL báo lỗi (tràn kiểu, ký tự NUL) thành 500 (spec exercise-wiki §6 mục 8).
    """
    row = None
    if _DIGITS.fullmatch(id_or_slug):
        exercise_id = _exercise_id_in_range(id_or_slug)
        if exercise_id is not None:
            row = await crud.get_published_exercise_by_id(db, exercise_id)
    elif _SLUG_FORMAT.fullmatch(id_or_slug):
        row = await crud.get_published_exercise_by_slug(db, id_or_slug)
    if row is None:
        raise NotFoundError("exercise_not_found", "Không tìm thấy bài tập")
    return row


def _models(schema: type[_SchemaT], rows: list[Any]) -> list[_SchemaT]:
    # Cột của crud đã đặt alias trùng tên field schema.
    return [schema.model_validate(dict(row)) for row in rows]


def _difficulty(row: Any) -> DifficultySchema:
    return DifficultySchema(
        id=row["difficulty_id"], code=row["difficulty_code"], name=row["difficulty_name"], rank=row["difficulty_rank"]
    )


async def get_exercise_detail(db: AsyncSession, id_or_slug: str) -> ExerciseDetailResponse:
    """Chi tiết kỹ thuật bài đã xuất bản: độ khó, nhóm cơ, thiết bị, các bước, lỗi sai, media (không URL)."""
    row = await _get_published_exercise(db, id_or_slug)
    exercise_id = row["id"]
    return ExerciseDetailResponse(
        id=exercise_id,
        slug=row["slug"],
        name=row["name"],
        name_en=row["name_en"],
        description=row["description"],
        category=row["category"],
        mechanic=row["mechanic"],
        force_type=row["force_type"],
        is_unilateral=row["is_unilateral"],
        met_value=row["met_value"],
        supports_ai_tracking=row["supports_ai_tracking"],
        difficulty=_difficulty(row),
        muscles=_models(ExerciseMuscleSchema, await crud.list_exercise_muscles(db, exercise_id)),
        equipment=_models(ExerciseEquipmentSchema, await crud.list_exercise_equipment(db, exercise_id)),
        instructions=_models(ExerciseInstructionSchema, await crud.list_exercise_instructions(db, exercise_id)),
        mistakes=_models(ExerciseMistakeSchema, await crud.list_exercise_mistakes(db, exercise_id)),
        media=_models(ExerciseMediaSchema, await crud.list_exercise_media(db, exercise_id)),
    )


async def list_exercise_alternatives(
    db: AsyncSession, id_or_slug: str, query: ExerciseAlternativesQuery
) -> Page[ExerciseAlternativeResponse]:
    """Bài thay thế cho bài đã xuất bản, bỏ bài cần thiết bị đang bận; cursor `{"offset": n}`.

    Bài gốc được kiểm tra trước vì `catalog.fn_suggest_alternatives` trả rỗng thay vì báo lỗi (spec §6 mục 8).
    """
    offset = _int_from_cursor(query.cursor, "offset") if query.cursor is not None else 0
    exercise = await _get_published_exercise(db, id_or_slug)
    # Hàm SQL chỉ có LIMIT: lấy từ đầu tới hết trang này (+1 để biết has_more) rồi bỏ phần trước offset.
    # Chặn ở 2^31-1 vì `p_limit` là `integer`, offset lớn cộng thêm sẽ tràn kiểu thành lỗi 500.
    fetch_limit = min(offset + query.limit + 1, _INT4_MAX)
    rows = await crud.list_exercise_alternatives(
        db, exercise["id"], query.unavailable_equipment_id, limit=fetch_limit
    )
    alternatives = _models(ExerciseAlternativeResponse, rows[offset:])
    return build_page(alternatives, query.limit, lambda item: item, lambda _item: {"offset": offset + query.limit})


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


async def list_exercises_for_ai_label(db: AsyncSession, ai_label: str, limit: int = 20) -> list[EquipmentExerciseSchema]:
    """Bài tập dùng thiết bị mà model nhận diện trả về nhãn `ai_label`, sắp theo độ khó rồi tên.

    Dành cho module Nhận diện thiết bị (chức năng 7) gọi qua service, không có route riêng. Hàm SQL tự
    chuẩn hoá nhãn (`lower(btrim(...))`); thiết bị đã xoá mềm hoặc nhãn không có → danh sách rỗng.
    """
    return _models(EquipmentExerciseSchema, await crud.list_exercises_for_ai_label(db, ai_label, limit=limit))
