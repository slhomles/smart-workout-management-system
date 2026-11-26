"""Endpoint module Catalog/Wiki (chức năng 1): /exercises, /muscle-groups, /equipment.

Một `router` gộp các router con theo tiền tố của doc 05 §6.3; mỗi router con mang tag Swagger riêng (doc 05 §4).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.schemas.base import ERROR_RESPONSES, Page
from app.schemas.catalog import (
    EquipmentQuery,
    EquipmentResponse,
    ExerciseAlternativeResponse,
    ExerciseAlternativesQuery,
    ExerciseDetailResponse,
    ExerciseSearchQuery,
    ExerciseSummaryResponse,
    MuscleGroupResponse,
)
from app.services import catalog_service

router = APIRouter()
exercises_router = APIRouter(prefix="/exercises", tags=["Exercises"])
muscle_groups_router = APIRouter(prefix="/muscle-groups", tags=["Exercises"])
equipment_router = APIRouter(prefix="/equipment", tags=["Equipment"])


# --- Bài tập ---
@exercises_router.get(
    "",
    response_model=Page[ExerciseSummaryResponse],
    status_code=200,
    responses=ERROR_RESPONSES,
    summary="Tìm và lọc bài tập, sắp theo độ khó tăng dần",
    description=(
        "Quyền: `exercise:read`. Chỉ trả bài đã xuất bản, qua `catalog.fn_search_exercises`. "
        "`q` khớp tên bài, nhóm cơ, thiết bị và từ đồng nghĩa, không phân biệt dấu và hoa thường; "
        "`muscle_group_id` (lặp param, chọn nhóm cha gồm cả nhóm con) kết hợp `is_primary_only`; "
        "`available_equipment_id` (lặp param) chỉ giữ bài mà mọi thiết bị bắt buộc đều có sẵn; "
        "`max_difficulty_rank` giới hạn độ khó. Sắp theo độ khó tăng dần, rồi mức khớp từ khoá, rồi tên; "
        "không có tham số `sort`. Phân trang cursor (`limit` 1–100, mặc định 20). "
        "Tham số hoặc cursor sai → 422 `validation_error`."
    ),
)
async def search_exercises(
    query: Annotated[ExerciseSearchQuery, Query()],
    _: CurrentUser = Depends(require_permission("exercise", "read")),
    db: AsyncSession = Depends(get_db),
) -> Page[ExerciseSummaryResponse]:
    """Tìm kiếm và lọc đa điều kiện cho bước 1–2 của Wiki."""
    return await catalog_service.search_exercises(db, query)


@exercises_router.get(
    "/{id_or_slug}",
    response_model=ExerciseDetailResponse,
    status_code=200,
    responses=ERROR_RESPONSES,
    summary="Chi tiết kỹ thuật bài tập theo id hoặc slug",
    description=(
        "Quyền: `exercise:read`. `id_or_slug` toàn chữ số thì tra theo `id`, ngược lại tra theo `slug`. "
        "Gồm độ khó, nhóm cơ kèm vai trò và tỷ lệ kích hoạt, thiết bị (bắt buộc trước, tuỳ chọn sau), các bước, "
        "lỗi sai thường gặp và metadata media minh hoạ (`media_id`, không có URL). "
        "Bài không tồn tại, chưa xuất bản, đã lưu trữ hoặc đã xoá → 404 `exercise_not_found`."
    ),
)
async def get_exercise_detail(
    id_or_slug: Annotated[str, Path(description="`id` (số nguyên) hoặc `slug` của bài tập, vd `dumbbell-row`")],
    _: CurrentUser = Depends(require_permission("exercise", "read")),
    db: AsyncSession = Depends(get_db),
) -> ExerciseDetailResponse:
    """Chi tiết kỹ thuật cho bước 3 của Wiki."""
    return await catalog_service.get_exercise_detail(db, id_or_slug)


@exercises_router.get(
    "/{id_or_slug}/alternatives",
    response_model=Page[ExerciseAlternativeResponse],
    status_code=200,
    responses=ERROR_RESPONSES,
    summary="Gợi ý bài thay thế cùng nhóm cơ, bỏ bài cần thiết bị đang bận",
    description=(
        "Quyền: `exercise:read`. Gợi ý bài đã xuất bản cùng tác động lên nhóm cơ chính của bài gốc, qua "
        "`catalog.fn_suggest_alternatives`. Sắp theo `score` giảm dần rồi theo tên: `score` = `muscle_overlap` "
        "(độ trùng nhóm cơ, 0–1) + 0,5 nếu là bài thay thế do biên tập viên chọn (`is_curated`) + 0,1 nếu cùng kiểu "
        "compound/isolation − 0,05 × chênh lệch độ khó, nên bài biên tập viên chọn được ưu tiên. "
        "`unavailable_equipment_id` (lặp param) là thiết bị đang bận: loại bài cần thiết bị **bắt buộc** nằm trong "
        "danh sách (thiết bị tuỳ chọn không tính). Phân trang cursor (`limit` 1–100, mặc định 20). "
        "Bài gốc không tồn tại, chưa xuất bản, đã lưu trữ hoặc đã xoá → 404 `exercise_not_found`; "
        "tham số hoặc cursor sai → 422 `validation_error`."
    ),
)
async def list_exercise_alternatives(
    id_or_slug: Annotated[str, Path(description="`id` (số nguyên) hoặc `slug` của bài gốc, vd `dumbbell-row`")],
    query: Annotated[ExerciseAlternativesQuery, Query()],
    _: CurrentUser = Depends(require_permission("exercise", "read")),
    db: AsyncSession = Depends(get_db),
) -> Page[ExerciseAlternativeResponse]:
    """Bài thay thế khi máy đang bận, cho bước 4 của Wiki."""
    return await catalog_service.list_exercise_alternatives(db, id_or_slug, query)


# --- Nhóm cơ ---
@muscle_groups_router.get(
    "",
    response_model=Page[MuscleGroupResponse],
    status_code=200,
    responses=ERROR_RESPONSES,
    summary="Cây nhóm cơ (nút gốc kèm nhóm cơ con)",
    description=(
        "Quyền: `muscle_group:read`. Trả cây trong **một trang duy nhất** (`has_more=false`, "
        "`next_cursor=null`), không nhận `limit`/`cursor`. Nút gốc và `children` sắp theo `display_order, id`; "
        "`body_region` chỉ có ở nút gốc, nút con là `null`."
    ),
)
async def list_muscle_groups(
    _: CurrentUser = Depends(require_permission("muscle_group", "read")),
    db: AsyncSession = Depends(get_db),
) -> Page[MuscleGroupResponse]:
    """Cây nhóm cơ cho màn hình khởi tạo tìm kiếm của Wiki."""
    return await catalog_service.list_muscle_groups(db)


# --- Thiết bị ---
@equipment_router.get(
    "",
    response_model=Page[EquipmentResponse],
    status_code=200,
    responses=ERROR_RESPONSES,
    summary="Danh sách thiết bị kèm nhóm thiết bị và từ đồng nghĩa",
    description=(
        "Quyền: `equipment:read`. Bỏ thiết bị đã xoá mềm; sắp theo `id` tăng dần, phân trang cursor "
        "(`limit` 1–100, mặc định 20). Lọc tuỳ chọn `category_id`; nhóm không tồn tại trả `data=[]`. "
        "`synonyms` chỉ gồm từ đồng nghĩa, không có nhãn AI. Tham số hoặc cursor sai → 422 `validation_error`."
    ),
)
async def list_equipment(
    query: Annotated[EquipmentQuery, Query()],
    _: CurrentUser = Depends(require_permission("equipment", "read")),
    db: AsyncSession = Depends(get_db),
) -> Page[EquipmentResponse]:
    """Danh sách thiết bị cho bộ lọc "thiết bị sẵn có" của Wiki."""
    return await catalog_service.list_equipment(db, query)


# include_router chép route tại thời điểm gọi, nên phải đặt sau khi router con đã khai báo đủ route.
router.include_router(muscle_groups_router)
router.include_router(equipment_router)
router.include_router(exercises_router)
