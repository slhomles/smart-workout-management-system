"""Đóng watermark (ngày chụp + số đo) và tạo thumbnail cho ảnh tiến độ bằng Pillow.

Hàm thuần: nhận/trả bytes, không chạm DB hay kho lưu trữ. Hàm chặn (CPU) — service gọi qua run_in_threadpool.
"""

import io
from datetime import date

from PIL import Image, ImageDraw, ImageOps

from app.utils.report_card import _font

WATERMARK_MAX_SIDE = 2048
THUMBNAIL_MAX_SIDE = 400
JPEG_QUALITY = 85
PART_SEPARATOR = " · "
# Tỉ lệ theo cạnh ngắn để chữ và lề đọc được như nhau trên ảnh dọc lẫn ảnh ngang.
FONT_SIZE_RATIO = 30
MIN_FONT_SIZE = 12
BOX_FILL = (0, 0, 0, 150)
TEXT_FILL = (255, 255, 255, 255)


def _decimal_comma(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def watermark_text(taken_date: date, weight_kg: float | None, body_fat_pct: float | None) -> str:
    """Dựng chuỗi watermark `dd/mm/yyyy · 70,0 kg · 18,4% mỡ`; bỏ phần số đo nào là None."""
    parts = [taken_date.strftime("%d/%m/%Y")]
    if weight_kg is not None:
        parts.append(f"{_decimal_comma(weight_kg)} kg")
    if body_fat_pct is not None:
        parts.append(f"{_decimal_comma(body_fat_pct)}% mỡ")
    return PART_SEPARATOR.join(parts)


def _open_upright_rgb(image_bytes: bytes) -> Image.Image:
    with Image.open(io.BytesIO(image_bytes)) as source:
        # in_place=True vì bản không in-place có kiểu trả `Image | None` trong stub của Pillow.
        ImageOps.exif_transpose(source, in_place=True)
        return source.convert("RGB")


def _to_jpeg(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()


def _draw_corner_label(image: Image.Image, text: str) -> Image.Image:
    font_size = max(MIN_FONT_SIZE, min(image.size) // FONT_SIZE_RATIO)
    padding = font_size // 2
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _font(font_size)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    box_right = image.width - padding
    box_bottom = image.height - padding
    box_left = box_right - (right - left) - 2 * padding
    box_top = box_bottom - (bottom - top) - 2 * padding
    draw.rectangle((box_left, box_top, box_right, box_bottom), fill=BOX_FILL)
    draw.text((box_left + padding - left, box_top + padding - top), text, font=font, fill=TEXT_FILL)
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def render_watermark(image_bytes: bytes, text: str) -> bytes:
    """Xoay theo EXIF, thu nhỏ cạnh dài ≤ 2048 px, đóng `text` trên nền mờ ở góc dưới phải; trả JPEG q85."""
    image = _open_upright_rgb(image_bytes)
    # thumbnail() chỉ thu nhỏ, không phóng to, và giữ tỉ lệ — đúng quy cách ảnh watermark.
    image.thumbnail((WATERMARK_MAX_SIDE, WATERMARK_MAX_SIDE), Image.Resampling.LANCZOS)
    return _to_jpeg(_draw_corner_label(image, text))


def make_thumbnail(image_bytes: bytes) -> bytes:
    """Thu nhỏ ảnh (đã watermark) sao cho cạnh dài ≤ 400 px, giữ tỉ lệ; trả JPEG."""
    image = _open_upright_rgb(image_bytes)
    image.thumbnail((THUMBNAIL_MAX_SIDE, THUMBNAIL_MAX_SIDE), Image.Resampling.LANCZOS)
    return _to_jpeg(image)
