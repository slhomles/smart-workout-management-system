"""Nghiệp vụ phát media (spec be-media-delivery): quyền xem một file media và URL tạm để tải.

DB chỉ lưu (provider, bucket, object_key), không lưu URL (design-overview §2): URL sinh lúc đọc.
Gọi `storage_service.*` và `permission_service.*` qua thuộc tính module để test thay thế được (monkeypatch).
Module chỉ đọc DB nên không commit.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, PermissionDeniedError, ServiceUnavailableError
from app.crud import media as crud
from app.models.media import MediaFile
from app.schemas.base import ErrorDetail
from app.schemas.media import MediaResponse
from app.services import permission_service, storage_service

logger = logging.getLogger("app.media")

# Thời hạn presigned URL; là hằng số ở đây vì `core/config.py` là file core (spec §6 ý 5, Q3).
PRESIGNED_URL_TTL_SECONDS = 900
# Loại nội dung danh mục → permission đọc tương ứng (spec §6 ý 3; doc 04 §2.3).
CATALOG_READ_PERMISSIONS = {
    crud.EXERCISE_REFERENCE: "exercise:read",
    crud.EQUIPMENT_REFERENCE: "equipment:read",
}
# Thông điệp cố định: không lộ tên exception/chi tiết nội bộ (Claude_api_respone §3); chi tiết nằm ở log.
STORAGE_DOWN_MESSAGE = "Kho lưu trữ media tạm thời không khả dụng"
SIGNING_FAILED_DETAIL = "Không tạo được đường dẫn tải file từ kho lưu trữ"
READ_FAILED_DETAIL = "Không đọc được file từ kho lưu trữ"
FILE_MISSING_MESSAGE = "File media không còn trên kho lưu trữ"


async def _is_owned_by(db: AsyncSession, media: MediaFile, user_id: uuid.UUID) -> bool:
    # File watermark/thumbnail do hệ thống sinh có uploaded_by_user_id NULL; chủ sở hữu suy ra từ ảnh tiến độ.
    if media.uploaded_by_user_id == user_id:
        return True
    return await crud.is_progress_photo_media_of_user(db, media.id, user_id)


async def _can_read_catalog_media(db: AsyncSession, user_id: uuid.UUID, reference_kinds: set[str]) -> bool:
    required = {CATALOG_READ_PERMISSIONS[kind] for kind in reference_kinds}
    granted = await permission_service.get_permissions(db, user_id)
    return not required.isdisjoint(granted)


async def get_accessible_media(db: AsyncSession, user_id: uuid.UUID, media_id: uuid.UUID) -> MediaFile:
    """Media `user_id` được xem, theo đúng thứ tự quy tắc truy cập (spec §6 ý 3); dùng chung cho mọi route /media.

    1. Không tồn tại, đã xoá mềm hoặc chưa `available` → 404.
    2. Thuộc user (người tải lên, hoặc file của ảnh tiến độ của user) → cho phép, không kiểm permission.
    3. Media danh mục còn hiển thị → cần ít nhất một trong `exercise:read`/`equipment:read` tương ứng, thiếu → 403.
    4. Còn lại → 404. Mọi 404 dùng cùng một body để không lộ media có tồn tại hay không (doc 05 §2.6).
    """
    media = await crud.get_available_media(db, media_id)
    if media is None:
        raise NotFoundError()
    if await _is_owned_by(db, media, user_id):
        return media
    reference_kinds = await crud.get_catalog_reference_kinds(db, media_id)
    if not reference_kinds:
        raise NotFoundError()
    if not await _can_read_catalog_media(db, user_id, reference_kinds):
        raise PermissionDeniedError()
    return media


async def _presign(media: MediaFile) -> tuple[str, datetime]:
    # Mốc hết hạn tính từ ngay trước khi ký nên không muộn hơn hạn thật của chữ ký.
    signed_at = datetime.now(timezone.utc)
    try:
        url = await storage_service.presign_get_url(media.bucket, media.object_key, PRESIGNED_URL_TTL_SECONDS)
    except Exception as exc:
        logger.exception("media: không ký được presigned URL media_id=%s", media.id)
        raise ServiceUnavailableError(
            STORAGE_DOWN_MESSAGE,
            [ErrorDetail(field="storage", message=SIGNING_FAILED_DETAIL, code="down")],
        ) from exc
    return url, signed_at + timedelta(seconds=PRESIGNED_URL_TTL_SECONDS)


async def _build_url(media: MediaFile) -> tuple[str, datetime | None]:
    """URL tạm: presigned S3 (có hạn) hoặc route nội dung tương đối khi lưu local (không hạn)."""
    # Đọc settings lúc gọi (không lưu lúc import) để cấu hình runtime và test monkeypatch đều có hiệu lực.
    if get_settings().STORAGE_BACKEND == "s3":
        return await _presign(media)
    # Đường dẫn tương đối, không dựng từ header Host để tránh host-header injection (spec §6 ý 5).
    return f"/api/v1/media/{media.id}/content", None


async def get_media(db: AsyncSession, user_id: uuid.UUID, media_id: uuid.UUID) -> MediaResponse:
    """Metadata của media kèm URL tạm; chỉ ký URL sau khi đã qua phân quyền."""
    media = await get_accessible_media(db, user_id, media_id)
    url, url_expires_at = await _build_url(media)
    return MediaResponse(
        id=media.id,
        mime_type=media.mime_type,
        size_bytes=media.size_bytes,
        width_px=media.width_px,
        height_px=media.height_px,
        duration_ms=media.duration_ms,
        url=url,
        url_expires_at=url_expires_at,
        created_at=media.created_at,
    )


async def get_media_content(db: AsyncSession, user_id: uuid.UUID, media_id: uuid.UUID) -> tuple[bytes, str]:
    """Nội dung file media và `mime_type` của nó; chỉ đọc kho sau khi đã qua phân quyền (spec §6 ý 7).

    File không còn trên kho → 404 `not_found` với message riêng: user đã được phép xem media này nên message
    khác không lộ media có tồn tại hay không (spec §6 ý 2). Kho lỗi → 503 `service_unavailable`.
    """
    media = await get_accessible_media(db, user_id, media_id)
    try:
        data = await storage_service.read_object(media.bucket, media.object_key)
    except Exception as exc:
        # Không log object_key: key của media cá nhân có thể chứa định danh user.
        logger.exception("media: không đọc được file từ kho media_id=%s", media.id)
        raise ServiceUnavailableError(
            STORAGE_DOWN_MESSAGE,
            [ErrorDetail(field="storage", message=READ_FAILED_DETAIL, code="down")],
        ) from exc
    if data is None:
        raise NotFoundError("not_found", FILE_MISSING_MESSAGE)
    return data, media.mime_type
