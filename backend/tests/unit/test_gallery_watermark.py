"""Unit test hàm thuần đóng watermark/tạo thumbnail ảnh tiến độ (GAL-05), không cần DB."""

import io
from datetime import date

import pytest
from PIL import Image

from app.utils import photo_watermark

BASE_COLOR = (40, 120, 200)


def _encode(image: Image.Image, image_format: str) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def _jpeg(width: int, height: int) -> bytes:
    return _encode(Image.new("RGB", (width, height), BASE_COLOR), "JPEG")


def _png(width: int, height: int) -> bytes:
    return _encode(Image.new("RGBA", (width, height), (*BASE_COLOR, 255)), "PNG")


def _max_channel_diff(pixel: tuple[int, ...]) -> int:
    return max(abs(channel - base) for channel, base in zip(pixel[:3], BASE_COLOR, strict=True))


def _quadrant_diffs(image: Image.Image, left: int, top: int) -> list[int]:
    width, height = image.size
    box = (left, top, left + width // 2, top + height // 2)
    return [_max_channel_diff(pixel) for pixel in image.crop(box).getdata()]


@pytest.mark.tc("GAL-05")
@pytest.mark.parametrize(
    ("taken_date", "weight_kg", "body_fat_pct", "expected"),
    [
        (date(2026, 10, 5), 70.0, 18.4, "05/10/2026 · 70,0 kg · 18,4% mỡ"),
        (date(2026, 1, 9), 65.0, None, "09/01/2026 · 65,0 kg"),
        (date(2026, 1, 9), None, None, "09/01/2026"),
    ],
)
def test_watermark_text_with_optional_measurements_joins_present_parts(taken_date, weight_kg, body_fat_pct, expected):
    assert photo_watermark.watermark_text(taken_date, weight_kg, body_fat_pct) == expected


@pytest.mark.tc("GAL-05")
def test_render_watermark_small_jpeg_keeps_size_and_marks_bottom_right():
    result = photo_watermark.render_watermark(_jpeg(1200, 1600), "05/10/2026 · 70,0 kg · 18,4% mỡ")

    assert isinstance(result, bytes)
    image = Image.open(io.BytesIO(result))
    assert image.format == "JPEG"
    assert image.size == (1200, 1600)
    rgb = image.convert("RGB")
    assert max(_quadrant_diffs(rgb, 0, 0)) <= 8
    assert max(_quadrant_diffs(rgb, 600, 800)) > 60


@pytest.mark.tc("GAL-05")
def test_render_watermark_large_png_downscales_to_rgb_jpeg():
    result = photo_watermark.render_watermark(_png(3000, 4000), "x")

    image = Image.open(io.BytesIO(result))
    assert image.format == "JPEG"
    assert image.mode == "RGB"
    assert image.size == (1536, 2048)


@pytest.mark.tc("GAL-05")
def test_make_thumbnail_from_watermarked_photo_returns_jpeg_with_long_side_400():
    watermarked = photo_watermark.render_watermark(_jpeg(1200, 1600), "05/10/2026 · 70,0 kg · 18,4% mỡ")

    thumbnail = Image.open(io.BytesIO(photo_watermark.make_thumbnail(watermarked)))

    assert thumbnail.format == "JPEG"
    assert thumbnail.size == (300, 400)
