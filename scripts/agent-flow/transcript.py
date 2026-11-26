"""Đọc transcript của Claude Code và phân loại thời gian theo từng lệnh (dùng cho timeline.py).

Transcript nằm ở `~/.claude/projects/<thư mục làm việc mã hoá>/<session>.jsonl`, mỗi entry có `timestamp`;
tool_use ghép với tool_result theo id. Định dạng này là nội bộ của Claude Code nên mọi lỗi đọc đều bị bỏ qua.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from collections import defaultdict
from pathlib import Path

MODEL_LABEL = "model suy nghĩ/viết"
WAIT_LABEL = "chờ test chạy nền"
PRIORITY = ["implementer", WAIT_LABEL, "cổng check_done", "pytest", "ruff/mypy", "commit",
            "đọc tài liệu/code", "ghi state/journal", "lệnh khác"]
COMMAND_LABELS = [("check_done", "cổng check_done"), ("flow_commit", "commit"), ("pytest", "pytest"),
                  ("ruff", "ruff/mypy"), ("mypy", "ruff/mypy")]
READ_TOOLS, WRITE_TOOLS, SHELL_TOOLS = {"Read", "Grep", "Glob"}, {"Write", "Edit"}, {"Bash", "PowerShell"}
WAIT_LOOPS = ("for ", "until ", "while ")
NOTIFICATION_ID = re.compile(r"<tool-use-id>([^<]+)</tool-use-id>")
SECRET_PATTERNS = [
    (re.compile(r"://[^/\s:@]+:[^/\s@]+@"), "://***@"),
    (re.compile(r"(?i)\b(password|passwd|pwd|token|secret|api[_-]?key)\s*[=:]\s*\S+"), r"\1=***"),
    (re.compile(r"\beyJ[\w.\-]{20,}"), "***"),
    (re.compile(r"\b[A-Fa-f0-9]{32,}\b|\b[A-Za-z0-9_]{40,}\b"), "***"),
]


def transcript_dir(worktree: Path) -> Path:
    """Claude mã hoá đường dẫn thư mục làm việc: mọi ký tự không phải chữ/số thành `-`."""
    root = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
    name = re.sub(r"[^A-Za-z0-9]", "-", str(worktree))
    exact = root / name
    if exact.exists() or not root.exists():
        return exact
    return next((p for p in root.iterdir() if p.name.lower() == name.lower()), exact)


def read_entries(path: Path) -> list[dict]:
    """Đọc file jsonl, bỏ qua dòng hỏng (file có thể đang được ghi dở)."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    entries = []
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def entry_time(entry: dict) -> float | None:
    raw = entry.get("timestamp")
    if not isinstance(raw, str):
        return None
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def content_blocks(entry: dict) -> list[dict]:
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def pair_calls(entries: list[dict]) -> dict[str, dict]:
    """Ghép tool_use với tool_result theo id; lệnh chưa có kết quả (đang chạy) có `end = None`."""
    calls: dict[str, dict] = {}
    for entry in entries:
        moment = entry_time(entry)
        for block in content_blocks(entry) if moment is not None else []:
            if block.get("type") == "tool_use":
                calls.setdefault(block.get("id"), {"name": str(block.get("name")),
                                                    "input": block.get("input") or {},
                                                    "start": moment, "end": None})
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in calls:
                calls[block["tool_use_id"]]["end"] = moment
    return calls


def entry_text(entry: dict) -> str:
    raw = entry.get("content")
    message = entry.get("message")
    if raw is None and isinstance(message, dict):
        raw = message.get("content")
    if isinstance(raw, list):
        return " ".join(str(b.get("text", "")) for b in raw if isinstance(b, dict))
    return raw if isinstance(raw, str) else ""


def background_finishes(entries: list[dict]) -> dict[str, float]:
    """Giờ hoàn tất của lệnh chạy nền, lấy từ thông báo `<task-notification>` (khoá theo tool-use-id)."""
    finished: dict[str, float] = {}
    for entry in entries:
        moment = entry_time(entry)
        text = entry_text(entry) if moment is not None else ""
        if "<task-notification>" in text:
            for call_id in NOTIFICATION_ID.findall(text):
                finished.setdefault(call_id, moment)
    return finished


def tool_calls(entries: list[dict], is_live: bool = False) -> list[dict]:
    """Lệnh chạy nền trả kết quả ngay ("đang chạy nền") nên kết thúc thật là lúc có thông báo hoàn tất.

    Chưa có thông báo: phiên đã kết thúc thì giữ giờ trả kết quả, phiên đang chạy thì coi là còn chạy."""
    calls = pair_calls(entries)
    finishes = background_finishes(entries)
    for call_id, call in calls.items():
        if call["input"].get("run_in_background") is True:
            if call_id in finishes:
                call["end"] = finishes[call_id]
            elif is_live:
                call["end"] = None
    return list(calls.values())


def classify_command(command: str) -> str:
    if "sleep" in command and any(loop in command for loop in WAIT_LOOPS):
        return WAIT_LABEL  # vòng lặp `sleep` đợi file kết quả của test/cổng đang chạy nền
    return next((label for needle, label in COMMAND_LABELS if needle in command), "lệnh khác")


def classify(call: dict) -> str:
    name = call["name"]
    if name == "Agent":
        return "implementer"
    if name in READ_TOOLS:
        return "đọc tài liệu/code"
    if name in WRITE_TOOLS:
        return "ghi state/journal"
    if name in SHELL_TOOLS:
        return classify_command(str(call["input"].get("command") or ""))
    return "lệnh khác"


def call_spans(calls: list[dict], end: float) -> list[tuple[float, float, str]]:
    return [(c["start"], c["end"] if c["end"] is not None else end, classify(c)) for c in calls]


def cut_points(spans: list[tuple[float, float, str]], start: float, end: float) -> list[float]:
    points = {start, end}
    for left, right, _ in spans:
        points.update((left, right))
    return sorted(t for t in points if start <= t <= end)


def best_label(active: list[str]) -> str:
    return next((label for label in PRIORITY if label in active), MODEL_LABEL)


def sweep(calls: list[dict], start: float, end: float) -> dict[str, float]:
    """Mỗi đoạn thời gian tính cho nhóm ưu tiên nhất đang chạy; đoạn trống là model suy nghĩ/viết."""
    spans = call_spans(calls, end)
    cuts = cut_points(spans, start, end)
    totals: dict[str, float] = defaultdict(float)
    for left, right in zip(cuts, cuts[1:]):
        totals[best_label([label for s, e, label in spans if s <= left and e >= right])] += right - left
    return dict(totals)


def sanitize(text: str, limit: int = 90) -> str:
    """Rút gọn câu lệnh để hiển thị; che mật khẩu, token, chuỗi dài trông như khoá."""
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def describe(call: dict) -> str:
    data = call["input"]
    return sanitize(str(data.get("command") or data.get("description") or data.get("file_path") or call["name"]))
