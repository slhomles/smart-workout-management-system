"""Kiểm tra và giải mã ảnh upload trước khi suy luận (spec ai-equipment-classify §6 ý 4; 06-ai-contracts.md §2.4).

Chỉ tin định dạng thật mà Pillow nhận ra, bỏ qua `content_type` và tên file của part. Mọi ảnh sai đều thành
`400 bad_request` với đúng một phần tử `details` trỏ vào field `image`.
"""

import io
import logging

from PIL import Image, ImageOps

from app.core.errors import BadRequestError

logger = logging.getLogger(__name__)

# Bằng `MAX_IMAGE_BYTES` của backend (equipment_scan_service.py). Ảnh lớn hơn trả 400 chứ không 413,
# vì 413 không có trong bảng status của Claude_api_respone.md §4.
MAX_IMAGE_BYTES = 10 * 1024 * 1024
# 06 §2.4: part `image` là JPEG/PNG/WebP; tên định dạng theo `Image.format` của Pillow.
ACCEPTED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})

IMAGE_FIELD = "image"
INVALID_IMAGE_MESSAGE = "Ảnh gửi lên không hợp lệ"


def decode_image(data: bytes) -> Image.Image:
    """Kiểm kích thước và định dạng, rồi giải mã toàn bộ ảnh thành RGB đã xoay theo EXIF; ảnh sai thì ném 400."""
    if not data:
        raise _invalid_image("Ảnh rỗng, không có dữ liệu")
    if len(data) > MAX_IMAGE_BYTES:
        raise _invalid_image("Ảnh vượt quá dung lượng tối đa 10 MiB")
    image = _open_image(data)
    if image.format not in ACCEPTED_FORMATS:
        raise _invalid_image("Chỉ nhận ảnh JPEG, PNG hoặc WebP")
    return _to_upright_rgb(image)


def _open_image(data: bytes) -> Image.Image:
    try:
        return Image.open(io.BytesIO(data))
    # Header hỏng làm Pillow ném nhiều loại lỗi (`UnidentifiedImageError`, `SyntaxError`, `DecompressionBombError`
    # không kế thừa `OSError`...); lỗi nào cũng do ảnh gửi lên nên đều là 400.
    except Exception as exc:
        raise _undecodable_image(exc) from exc


def _to_upright_rgb(image: Image.Image) -> Image.Image:
    try:
        # Ảnh chụp từ điện thoại thường lưu chiều xoay trong EXIF; xoay lại để model thấy đúng chiều thật.
        # `exif_transpose` gọi `load()` nên buộc giải mã toàn bộ, nhờ vậy bắt được ảnh bị cắt cụt.
        ImageOps.exif_transpose(image, in_place=True)
        return image.convert("RGB")
    # Dữ liệu ảnh cắt cụt (`OSError`) hay EXIF hỏng (`SyntaxError`, `ValueError`...) cũng là lỗi của ảnh gửi lên.
    except Exception as exc:
        raise _undecodable_image(exc) from exc


def _undecodable_image(exc: Exception) -> BadRequestError:
    # Chỉ ghi tên lớp exception: bytes ảnh và tên file có thể chứa dữ liệu cá nhân (spec §6 ý 10; 06 §5).
    logger.info("equipment image could not be decoded: %s", type(exc).__name__)
    return _invalid_image("Không giải mã được ảnh")


def _invalid_image(reason: str) -> BadRequestError:
    return BadRequestError(INVALID_IMAGE_MESSAGE, [{"field": IMAGE_FIELD, "message": reason, "code": "value_error"}])
