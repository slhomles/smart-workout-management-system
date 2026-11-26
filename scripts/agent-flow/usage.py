"""Token đã dùng và hạn mức tài khoản Claude cho agent flow. Chỉ dùng thư viện chuẩn.

- Token/chi phí: lấy từ sự kiện `result` mà `claude -p` trả về (`usage`, `total_cost_usd`).
- Hạn mức: lấy từ sự kiện `rate_limit_event` của `claude -p --output-format stream-json --verbose`
  (cửa sổ 5 giờ và 7 ngày: phần trăm đã dùng + thời điểm reset). `--output-format json` KHÔNG có thông tin này.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import time
from pathlib import Path

ALERT_LEVELS = (0.8, 0.9, 0.95)  # cảnh báo riêng khi % đã dùng vượt các mức này (mỗi mức một lần)
WINDOW_NAMES = {"five_hour": "5 giờ", "seven_day": "7 ngày"}
_probe_cache: dict = {"at": 0.0, "info": None}


def parse_stream(out: str) -> tuple[dict, dict | None]:
    """Từ stdout của `claude -p` (json hoặc stream-json) trả (sự kiện result, rate_limit_info mới nhất)."""
    result: dict = {}
    rate_limit = None
    for line in (out or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "rate_limit_event" and isinstance(event.get("rate_limit_info"), dict):
            rate_limit = event["rate_limit_info"]
        elif event.get("type") == "result":
            result = event
    if not result:  # --output-format json: cả output là một object
        try:
            data = json.loads(out)
            result = data if isinstance(data, dict) else {}
        except (ValueError, TypeError):
            result = {}
    return result, rate_limit


def tokens_of(result: dict) -> dict:
    """Tổng token một lần gọi: đầu vào (gồm cache) + đầu ra, kèm chi phí quy đổi theo giá niêm yết."""
    u = result.get("usage") or {}
    inp = int(u.get("input_tokens") or 0) + int(u.get("cache_creation_input_tokens") or 0) \
        + int(u.get("cache_read_input_tokens") or 0)
    out = int(u.get("output_tokens") or 0)
    return {"total": inp + out, "output": out, "cost_usd": float(result.get("total_cost_usd") or 0.0)}


def add(a: dict | None, b: dict) -> dict:
    a = a or {"total": 0, "output": 0, "cost_usd": 0.0}
    return {"total": a["total"] + b["total"], "output": a["output"] + b["output"],
            "cost_usd": round(a["cost_usd"] + b["cost_usd"], 4)}


def human(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def format_tokens(t: dict | None) -> str:
    if not t:
        return "chưa có số liệu"
    return f"{human(t['total'])} token (đầu ra {human(t['output'])}) · ~{t['cost_usd']:.2f} USD giá niêm yết"


def windows(info: dict | None) -> dict[str, dict]:
    """{"five_hour": {...}, "seven_day": {...}} với utilization (0–1), resetsAt (epoch), status."""
    if not info:
        return {}
    wins = info.get("unifiedWindows")
    if isinstance(wins, dict) and wins:
        return {k: v for k, v in wins.items() if isinstance(v, dict)}
    kind = info.get("rateLimitType")
    return {kind: info} if kind else {}


def _reset_text(epoch) -> str:
    try:
        when = dt.datetime.fromtimestamp(int(epoch))
    except (TypeError, ValueError, OSError):
        return "?"
    same_day = when.date() == dt.date.today()
    return when.strftime("%H:%M") if same_day else when.strftime("%H:%M %d/%m")


def format_quota(info: dict | None) -> str:
    wins = windows(info)
    if not wins:
        return "hạn mức: chưa đọc được"
    parts = []
    for key in ("five_hour", "seven_day"):
        w = wins.get(key)
        if not w or w.get("utilization") is None:
            continue
        used = float(w["utilization"])
        icon = "⛔" if w.get("status") == "rejected" else ("⚠️" if used >= ALERT_LEVELS[0] else "")
        parts.append(f"{icon}{WINDOW_NAMES.get(key, key)}: còn {max(0, round((1 - used) * 100))}% "
                     f"(đã dùng {round(used * 100)}%, reset {_reset_text(w.get('resetsAt'))})")
    return "Hạn mức Claude: " + " · ".join(parts) if parts else "hạn mức: chưa đọc được"


def new_alerts(info: dict | None, already: list[str]) -> list[tuple[str, float, str]]:
    """Các mốc vừa vượt mà chưa báo: (cửa sổ, mức, tag). Tag gắn với giờ reset nên sang cửa sổ mới sẽ báo lại."""
    found = []
    for key, w in windows(info).items():
        used = w.get("utilization")
        if used is None:
            continue
        for level in ALERT_LEVELS:
            tag = f"{key}:{level}:{w.get('resetsAt')}"
            if float(used) >= level and tag not in already:
                found.append((key, level, tag))
    return found


def format_alert(info: dict, key: str, level: float) -> str:
    w = windows(info).get(key, {})
    return (f"🚨 Hạn mức Claude cửa sổ {WINDOW_NAMES.get(key, key)} đã dùng {round(float(w.get('utilization', 0)) * 100)}% "
            f"(vượt mốc {round(level * 100)}%), reset lúc {_reset_text(w.get('resetsAt'))}. "
            "Hết hạn mức thì flow tự chờ đến giờ reset; muốn dừng bớt: /auto off hoặc /stop &lt;module&gt;.")


def summarize_logs(paths: list[Path]) -> dict | None:
    """Cộng token của các log `claude -p` (spec-writer-N.log, iter-NNN.out.json)."""
    total = None
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        result, _ = parse_stream(text.split("\n---\n", 1)[0])
        if result.get("usage"):
            total = add(total, tokens_of(result))
    return total


def probe_quota(claude: str, max_age: float = 600) -> dict | None:
    """Đọc hạn mức bằng một lần gọi haiku rất nhỏ (cache max_age giây) khi không có flow nào đang chạy."""
    if _probe_cache["info"] is not None and time.time() - _probe_cache["at"] < max_age:
        return _probe_cache["info"]
    try:
        proc = subprocess.run(
            [claude, "-p", "Trả lời đúng một chữ: ok", "--model", "haiku", "--tools", "",
             "--output-format", "stream-json", "--verbose"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    except (OSError, subprocess.TimeoutExpired):
        return _probe_cache["info"]
    _, info = parse_stream(proc.stdout)
    if info is not None:
        _probe_cache.update(at=time.time(), info=info)
    return info if info is not None else _probe_cache["info"]
