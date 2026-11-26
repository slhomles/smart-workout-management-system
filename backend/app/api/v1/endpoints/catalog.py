"""Endpoint module Catalog/Wiki (chức năng 1): /exercises, /muscle-groups, /equipment.

Một `router` gộp các router con theo tiền tố của doc 05 §6.3; mỗi router con mang tag Swagger riêng (doc 05 §4).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.schemas.base import ERROR_RESPONSES, Page
from app.schemas.catalog import (
    EquipmentQuery,
    EquipmentResponse,
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
