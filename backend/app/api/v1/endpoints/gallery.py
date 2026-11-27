"""Endpoint Progress Gallery (chức năng 4): /progress-photos, /photo-comparisons.

Một `router` gộp các router con của module.
"""

from typing import Any

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.schemas.base import ERROR_RESPONSES, ErrorResponse, Page
from app.schemas.gallery import (
    CreatePhotoComparisonRequest,
    ListPhotoComparisonsQuery,
    ListProgressPhotosQuery,
    PhotoComparisonResponse,
    ProgressPhotoResponse,
    UploadProgressPhotoForm,
)
from app.services import gallery_service, photo_comparison_service

router = APIRouter()
progress_router = APIRouter(prefix="/progress-photos", tags=["Gallery"])
comparison_router = APIRouter(prefix="/photo-comparisons", tags=["Gallery"])

OWN = require_permission("progress_photo", "manage_own")
PERM = "Quyền: `progress_photo:manage_own`; chỉ thao tác trên ảnh của chính mình."
STORAGE_DOWN: dict[int | str, dict[str, Any]] = {
    503: {"model": ErrorResponse, "description": "`service_unavailable`: kho lưu trữ ảnh không khả dụng"},
}


@progress_router.post(
    "",
    response_model=ProgressPhotoResponse,
    status_code=201,
    responses={**ERROR_RESPONSES, **STORAGE_DOWN},
    summary="Tải ảnh tiến độ, tự đóng watermark ngày chụp – cân nặng – % mỡ",
    description=(
        PERM + " `multipart/form-data`: `file` (JPEG/PNG thật, ≤ 10 MB, ≤ 40 triệu điểm ảnh), `angle`, "
        "`capture_source` (mặc định `camera`), `taken_at` (có múi giờ, không muộn hơn giờ server + 5 phút; "
        "mặc định giờ server), `note` (≤ 500). Lưu ảnh gốc, đóng watermark số đo gần nhất trước lúc chụp "
        "và tạo thumbnail ngay trong request; xử lý ảnh lỗi vẫn trả 201 với `processing_status=failed`. "
        "Sai dữ liệu → 422 `validation_error`; kho lưu trữ lỗi → 503 `service_unavailable`."
    ),
)
async def upload_progress_photo(
    response: Response,
    file: UploadFile = File(..., description="Ảnh JPEG hoặc PNG"),
    form: UploadProgressPhotoForm = Depends(),
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> ProgressPhotoResponse:
    result = await gallery_service.upload_photo(db, current.id, file, form)
    response.headers["Location"] = f"/api/v1/progress-photos/{result.id}"
    return result


@progress_router.get(
    "",
    response_model=Page[ProgressPhotoResponse],
    responses=ERROR_RESPONSES,
    summary="Lưới ảnh tiến độ của tôi, mới chụp trước",
    description=(
        PERM + " Chỉ ảnh chưa xoá, sắp `taken_at` giảm dần; phân trang cursor (`limit` 1–100, mặc định 20). "
        "Lọc tuỳ chọn `angle` (front / side / back). Tham số sai → 422 `validation_error`."
    ),
)
async def list_progress_photos(
    query: ListProgressPhotosQuery = Depends(),
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> Page[ProgressPhotoResponse]:
    return await gallery_service.list_photos(db, current.id, query)


@comparison_router.post(
    "",
    response_model=PhotoComparisonResponse,
    status_code=201,
    responses={**ERROR_RESPONSES},
    summary="Lưu cặp ảnh Before/After để so sánh",
    description=(
        PERM + " JSON `before_photo_id`, `after_photo_id`, `title` (tuỳ chọn, ≤ 100). Hai ảnh phải khác nhau, "
        "đều là ảnh chưa xoá của chính mình, và ảnh Before chụp trước ảnh After; response nhúng đủ thông số "
        "hai ảnh. Sai dữ liệu hoặc ảnh không dùng được → 422 `validation_error`; cặp đã lưu → 409 `conflict`."
    ),
)
async def create_photo_comparison(
    body: CreatePhotoComparisonRequest,
    response: Response,
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> PhotoComparisonResponse:
    result = await photo_comparison_service.create_comparison(db, current.id, body)
    response.headers["Location"] = f"/api/v1/photo-comparisons/{result.id}"
    return result


@comparison_router.get(
    "",
    response_model=Page[PhotoComparisonResponse],
    responses=ERROR_RESPONSES,
    summary="Các cặp so sánh Before/After của tôi, mới lưu trước",
    description=(
        PERM + " Chỉ cặp có cả hai ảnh chưa xoá, sắp `created_at` giảm dần; phân trang cursor "
        "(`limit` 1–100, mặc định 20). Tham số sai → 422 `validation_error`."
    ),
)
async def list_photo_comparisons(
    query: ListPhotoComparisonsQuery = Depends(),
    current: CurrentUser = Depends(OWN),
    db: AsyncSession = Depends(get_db),
) -> Page[PhotoComparisonResponse]:
    return await photo_comparison_service.list_comparisons(db, current.id, query)


# Gộp sau khi khai báo route: include_router sao chép các route đang có tại thời điểm gọi.
router.include_router(progress_router)
router.include_router(comparison_router)
