"""`POST /equipment-recognition/classify` (06-ai-contracts.md §2.4): API nội bộ, không tiền tố `/api/v1`, không xác thực (06 §2)."""

from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.contracts import AiClassifyResult
from app.equipment.image_io import MAX_IMAGE_BYTES
from app.equipment.loader import register_equipment_model
from app.equipment.service import classify_image

router = APIRouter(prefix="/equipment-recognition", tags=["Equipment"])

# Đăng ký lúc import thay vì startup hook (spec ai-equipment-classify §6 ý 9, như ai-recovery-predict §6 ý 7):
# `main.py` là file core nên không thêm hook ở đó; `on_startup`/`lifespan` của router lại chạy sau fixture
# `clean_registry`, làm test `/health` kỳ vọng `models == {}` trượt. Import thì `uvicorn app.main:app` có
# `equipment` (chưa nạp, hiện `null`) ngay, còn test vẫn bắt đầu với registry trống.
register_equipment_model()


@router.post(
    "/classify",
    response_model=AiClassifyResult,
    status_code=200,
    summary="Phân loại thiết bị phòng tập từ một ảnh",
    description=(
        "API nội bộ, không xác thực (06-ai-contracts §2). Nhận `multipart/form-data` với part file `image` "
        "(JPEG/PNG/WebP, 1 byte đến 10 MiB; chỉ tin định dạng thật của ảnh, field khác bị bỏ qua). Trả tối đa 5 "
        "nhãn thuộc 27 `ai_label` (06 §2.5), `confidence` giảm dần. Mã lỗi: 400 `bad_request` (ảnh rỗng, quá "
        "10 MiB, sai định dạng, không giải mã được), 422 `validation_error` (thiếu part file `image`), "
        "500 `internal_error` (lỗi suy luận bất ngờ), 503 `service_unavailable` (model chưa nạp được)."
    ),
    responses={
        400: {"description": "bad_request: ảnh rỗng, quá 10 MiB, sai định dạng hoặc không giải mã được"},
        422: {"description": "validation_error: thiếu part file `image` (format lỗi Claude_api_respone §3)"},
        503: {"description": "service_unavailable: model nhận diện thiết bị chưa nạp được"},
    },
)
async def classify(image: Annotated[UploadFile, File()]) -> AiClassifyResult:
    """Phân loại thiết bị trong ảnh của part `image`."""
    # Đọc dư đúng 1 byte so với giới hạn: đủ để biết ảnh quá lớn mà không giữ cả file lớn trong bộ nhớ.
    data = await image.read(MAX_IMAGE_BYTES + 1)
    # Giải mã ảnh và suy luận tốn CPU, chạy trong threadpool để không chặn event loop.
    return await run_in_threadpool(classify_image, data)
