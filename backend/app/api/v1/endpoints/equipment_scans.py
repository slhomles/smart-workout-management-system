"""Endpoint /ai/equipment-scans (chức năng 7): nhận diện thiết bị phòng tập."""

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.schemas.base import ERROR_RESPONSES, ErrorResponse, Page
from app.schemas.equipment_scan import EquipmentScanResponse, EquipmentScanSummaryResponse
from app.services import equipment_scan_service

router = APIRouter(prefix="/ai/equipment-scans", tags=["AI"])

AI_USE = require_permission("ai", "use")


@router.post(
    "",
    response_model=EquipmentScanResponse,
    status_code=201,
    responses={
        **ERROR_RESPONSES,
        503: {"model": ErrorResponse, "description": "`service_unavailable`: dịch vụ nhận diện thiết bị không khả dụng"},
    },
    summary="Quét ảnh thiết bị phòng tập, nhận diện máy và gợi ý bài tập",
    description=(
        "Quyền: `ai:use`. `multipart/form-data`, field file `image` (JPEG/PNG thật, 1 byte – 10 MiB). "
        "Gửi ảnh sang AI service nhận diện, ánh xạ nhãn sang thiết bị trong danh mục, lưu lần quét của "
        "**chính user đang đăng nhập** cùng tối đa 5 dự đoán (sắp `confidence` giảm dần) rồi trả 201 + `Location`. "
        "Ảnh không được lưu. Khi top-1 đủ tin cậy (`is_confident`, ≥ 0.60) kèm `suggested_exercises` là các bài "
        "dùng thiết bị đó (sắp theo độ khó); chưa đủ tin cậy thì `[]`. "
        "Lỗi: 422 `validation_error` (thiếu `image`, sai định dạng, rỗng, quá 10 MiB, không phải ảnh), "
        "503 `service_unavailable` (AI service không gọi được hoặc trả dữ liệu sai), 401 `token_invalid`, "
        "403 `permission_denied`, 500 `internal_error`."
    ),
)
async def create_equipment_scan(
    response: Response,
    image: UploadFile = File(..., description="Ảnh chụp thiết bị, JPEG hoặc PNG, 1 byte – 10 MiB"),
    current: CurrentUser = Depends(AI_USE),
    db: AsyncSession = Depends(get_db),
) -> EquipmentScanResponse:
    """Quét ảnh thiết bị của chính user, lưu kết quả và trả gợi ý bài tập (chức năng 7, bước 2–4)."""
    result = await equipment_scan_service.create_scan(db, current.id, image)
    response.headers["Location"] = f"/api/v1/ai/equipment-scans/{result.id}"
    return result


@router.get(
    "",
    response_model=Page[EquipmentScanSummaryResponse],
    status_code=200,
    responses=ERROR_RESPONSES,
    summary="Lịch sử quét thiết bị của tôi (mới nhất trước)",
    description=(
        "Quyền: `ai:use`. Trả các lần quét của **chính user đang đăng nhập** (admin cũng chỉ thấy của mình), "
        "sắp `scanned_at` giảm dần rồi `id` giảm dần, phân trang cursor (`limit` 1–100, mặc định 20). "
        "Mỗi phần tử kèm thiết bị top-1, `confidence`, `is_confident` (≥ 0.60) và `resolved_equipment_id`. "
        "Lỗi: 422 `validation_error` (`limit`/`cursor` sai), 401 `token_invalid`, 403 `permission_denied`."
    ),
)
async def list_equipment_scans(
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    current: CurrentUser = Depends(AI_USE),
    db: AsyncSession = Depends(get_db),
) -> Page[EquipmentScanSummaryResponse]:
    """Lịch sử quét thiết bị của chính user, phân trang cursor."""
    return await equipment_scan_service.list_scans(db, current.id, limit=limit, cursor=cursor)
