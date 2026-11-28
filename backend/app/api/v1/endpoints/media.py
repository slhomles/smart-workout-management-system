"""Endpoint phát media (Gallery & Media): /media — metadata kèm URL tạm của ảnh, GIF, video."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user
from app.schemas.base import ERROR_RESPONSES, ErrorResponse
from app.schemas.media import MediaResponse
from app.services import media_service

router = APIRouter(prefix="/media", tags=["Gallery"])

ACCESS_RULES = (
    "Cần đăng nhập. Media cá nhân (ảnh tiến độ, ảnh watermark/thumbnail của ảnh đó, avatar, file tự tải lên) "
    "chỉ chủ sở hữu xem được; người khác → 404 `not_found`. Media danh mục (bài tập đã xuất bản, thiết bị) cần "
    "`exercise:read` (media bài tập) hoặc `equipment:read` (ảnh thiết bị); thiếu quyền → 403 `permission_denied`. "
    "File không tồn tại, chưa sẵn sàng hoặc đã xoá → 404 `not_found`."
)
STORAGE_DOWN: dict[int | str, dict[str, Any]] = {
    503: {"model": ErrorResponse, "description": "`service_unavailable`: kho lưu trữ media không khả dụng"},
}
FILE_CONTENT: dict[int | str, dict[str, Any]] = {
    200: {
        "content": {"image/*": {}, "video/*": {}},
        "description": "Nội dung file (không bọc JSON); `Content-Type` là `mime_type` của media",
    },
}


@router.get(
    "/{media_id}",
    response_model=MediaResponse,
    status_code=200,
    responses={**ERROR_RESPONSES, **STORAGE_DOWN},
    summary="Thông tin file media kèm URL tạm để tải",
    description=(
        ACCESS_RULES + " Lưu local: `url` là đường dẫn tương đối `/api/v1/media/{media_id}/content` (gọi kèm "
        "header Bearer), `url_expires_at` null. Lưu S3: `url` là presigned URL hết hạn sau 900 giây "
        "(`url_expires_at`). `media_id` không phải UUID → 422 `validation_error`; "
        "kho lưu trữ lỗi → 503 `service_unavailable`."
    ),
)
async def get_media(
    media_id: uuid.UUID,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MediaResponse:
    return await media_service.get_media(db, current.id, media_id)


@router.get(
    "/{media_id}/content",
    response_class=Response,
    status_code=200,
    responses={**ERROR_RESPONSES, **STORAGE_DOWN, **FILE_CONTENT},
    summary="Tải nội dung file media",
    description=(
        ACCESS_RULES + " Trả nội dung file (không bọc JSON), `Content-Type` là `mime_type` của media; dùng được "
        "cho cả lưu local và S3 (production nên dùng presigned `url` của `GET /media/{media_id}`). File không còn "
        "trên kho → 404 `not_found`. `media_id` không phải UUID → 422 `validation_error`; "
        "kho lưu trữ lỗi → 503 `service_unavailable`."
    ),
)
async def get_media_content(
    media_id: uuid.UUID,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    data, mime_type = await media_service.get_media_content(db, current.id, media_id)
    return Response(content=data, media_type=mime_type)
