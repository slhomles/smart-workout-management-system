"""Vẽ thẻ báo cáo tuần/tháng (PNG 1080×1920) bằng Pillow để lưu máy hoặc chia sẻ mạng xã hội."""

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.core.config import get_settings

WIDTH, HEIGHT = 1080, 1920
BG = (17, 24, 39)
CARD = (31, 41, 55)
TEXT = (243, 244, 246)
MUTED = (156, 163, 175)
ACCENT = (52, 211, 153)

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


@dataclass
class CardStat:
    label: str
    value: str


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    configured = get_settings().REPORT_FONT_PATH
    for path in ([configured] if configured else []) + _FONT_CANDIDATES:
        if path and Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def render_report_card(title: str, subtitle: str, display_name: str, stats: list[CardStat], footer: str) -> bytes:
    """Trả nội dung PNG. Hàm chặn (CPU) — gọi qua run_in_threadpool."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    f_title, f_sub, f_label, f_value = _font(76), _font(40), _font(36), _font(64)

    draw.text((80, 120), "SMART WORKOUT AI", font=f_sub, fill=ACCENT)
    draw.text((80, 200), title, font=f_title, fill=TEXT)
    draw.text((80, 310), subtitle, font=f_sub, fill=MUTED)
    draw.text((80, 370), display_name, font=f_sub, fill=TEXT)

    y = 500
    for stat in stats:
        draw.rounded_rectangle((60, y, WIDTH - 60, y + 190), radius=28, fill=CARD)
        draw.text((110, y + 30), stat.label, font=f_label, fill=MUTED)
        draw.text((110, y + 85), stat.value, font=f_value, fill=TEXT)
        y += 220

    draw.text((80, HEIGHT - 120), footer, font=f_label, fill=MUTED)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
