#!/usr/bin/env python3
"""Dựng timeline một phiên agent flow: thời gian đi đâu (implementer, chờ test, model suy nghĩ...).

Nguồn dữ liệu (chỉ đọc, không đổi cách chạy claude):
- transcript của Claude Code (xem transcript.py), gồm `<session>/subagents/agent-*.jsonl` cho từng lần gọi implementer;
- `state/timeline.jsonl` do run_flow.py ghi (cổng của runner, thời gian chờ hạn mức, ranh giới iteration).

Mọi lỗi đọc đều bị bỏ qua, không bao giờ làm sập runner.

Dùng tay:  python scripts/agent-flow/timeline.py <module> [--flow-root DIR]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from transcript import (MODEL_LABEL, classify, describe, entry_time, read_entries, sweep, tool_calls,
                        transcript_dir)

REPO = Path(__file__).resolve().parents[2]
INNER_RENAMES = {"ghi state/journal": "ghi code"}  # trong implementer, Write/Edit là sửa code
SUBAGENT_SLACK = 5.0  # giây: file subagent thuộc một lần gọi Agent nếu nằm trong cửa sổ ±5 s
MIN_SLOW_SECONDS = 20
MAX_SLOWEST = 5


# ------------------------------------------------------------------ một phiên (một iteration)

def load_subagents(session_dir: Path) -> list[dict]:
    subs = []
    for path in sorted((session_dir / "subagents").glob("agent-*.jsonl")):
        entries = read_entries(path)
        stamps = [t for t in map(entry_time, entries) if t is not None]
        if stamps:
            subs.append({"entries": entries, "start": min(stamps), "end": max(stamps), "mtime": path.stat().st_mtime})
    return subs


def match_subagent(window: dict, subs: list[dict], horizon: float) -> dict | None:
    end = window["end"] if window["end"] is not None else horizon
    return next((s for s in subs if s["start"] >= window["start"] - SUBAGENT_SLACK
                 and s["end"] <= end + SUBAGENT_SLACK), None)


def task_row(window: dict, subs: list[dict], horizon: float) -> dict:
    is_running = window["end"] is None
    row = {"task": str(window["input"].get("description") or "implementer")[:60],
           "seconds": (horizon if is_running else window["end"]) - window["start"],
           "is_running": is_running, "pytest_runs": 0, "inner": {}}
    sub = match_subagent(window, subs, horizon)
    if sub:
        inner = tool_calls(sub["entries"], is_running)
        inner_end = max(sub["end"], horizon) if is_running else sub["end"]  # lệnh đang chạy dở
        row["pytest_runs"] = sum(1 for c in inner if classify(c) == "pytest")
        row["inner"] = {INNER_RENAMES.get(k, k): v for k, v in sweep(inner, sub["start"], inner_end).items()}
    return row


def slowest(calls: list[dict], who: str, horizon: float) -> list[dict]:
    rows = []
    for call in calls:
        seconds = (call["end"] if call["end"] is not None else horizon) - call["start"]
        if call["name"] != "Agent" and seconds >= MIN_SLOW_SECONDS:
            rows.append({"who": who, "label": classify(call), "seconds": seconds, "text": describe(call)})
    return rows


def analyse_session(path: Path, now: float, is_live: bool = False) -> dict | None:
    entries = read_entries(path)
    stamps = [t for t in map(entry_time, entries) if t is not None]
    if not stamps:
        return None
    subs = load_subagents(path.with_suffix(""))
    start = min(stamps)
    end = max([max(stamps), *(s["end"] for s in subs)] + ([now] if is_live else []))
    calls = tool_calls(entries, is_live)
    top = slowest(calls, "orchestrator", end)
    for sub in subs:
        top += slowest(tool_calls(sub["entries"], is_live), "implementer", end)
    return {
        "session": path.stem, "start": start, "end": end, "seconds": end - start,
        "categories": sweep(calls, start, end),
        "tasks": [task_row(c, subs, end) for c in calls if c["name"] == "Agent"],
        "slowest": sorted(top, key=lambda r: -r["seconds"])[:MAX_SLOWEST],
    }


def session_summary(worktree: Path, session_id: str | None) -> dict | None:
    """Tóm tắt đúng một phiên (iteration vừa kết thúc) theo session_id của sự kiện `result`."""
    if not session_id:
        return None
    path = transcript_dir(worktree) / f"{session_id}.jsonl"
    return analyse_session(path, time.time()) if path.exists() else None


# ------------------------------------------------------------------ toàn module

def session_files(worktree: Path) -> list[Path]:
    folder = transcript_dir(worktree)
    return sorted(folder.glob("*.jsonl"), key=lambda p: p.stat().st_mtime) if folder.exists() else []


def total_seconds(events: list[dict]) -> float:
    return sum(float(e.get("seconds") or 0) for e in events)


def runner_summary(events: list[dict]) -> dict:
    gates = [e for e in events if e.get("kind") == "gate"]
    waits = [e for e in events if e.get("kind") == "wait"]
    cached = sum(1 for g in gates if g.get("cached"))
    return {"gate_runs": len(gates) - cached, "gate_cached": cached, "gate_seconds": total_seconds(gates),
            "wait_runs": len(waits), "wait_seconds": total_seconds(waits)}


def inner_activity(subs: list[dict], now: float) -> dict | None:
    """Lệnh mới nhất của implementer đang chạy (file subagent được ghi gần nhất)."""
    calls = tool_calls(max(subs, key=lambda s: s["mtime"])["entries"], True) if subs else []
    if not calls:
        return None
    last = calls[-1]
    return {"label": classify(last), "text": describe(last), "seconds": now - last["start"]}


def current_activity(worktree: Path, now: float) -> dict | None:
    """Việc agent đang làm: lệnh chưa có kết quả mới nhất; nếu là implementer thì thêm việc bên trong."""
    files = session_files(worktree)
    if not files:
        return None
    entries = read_entries(files[-1])
    open_calls = [c for c in tool_calls(entries, True) if c["end"] is None]
    if not open_calls:
        last_seen = max((t for t in map(entry_time, entries) if t is not None), default=now)
        return {"label": MODEL_LABEL, "seconds": now - last_seen, "text": "", "inner": None}
    call = open_calls[-1]
    activity = {"label": classify(call), "seconds": now - call["start"], "text": describe(call), "inner": None}
    if activity["label"] == "implementer":
        activity["inner"] = inner_activity(load_subagents(files[-1].with_suffix("")), now)
    return activity


def build_report(worktree: Path, state_dir: Path, is_running: bool = False) -> dict:
    now = time.time()
    events = read_entries(state_dir / "timeline.jsonl")  # sự kiện do run_flow.mark() ghi
    numbers = {e.get("session_id"): e.get("i") for e in events if e.get("kind") == "iteration"}
    files = session_files(worktree)
    sessions = []
    for index, path in enumerate(files):
        summary = analyse_session(path, now, is_live=is_running and index == len(files) - 1)
        if summary:
            summary["iteration"] = numbers.get(summary["session"])
            sessions.append(summary)
    return {"sessions": sessions, "runner": runner_summary(events),
            "current": current_activity(worktree, now) if is_running else None}


def main() -> int:
    from timeline_render import markdown

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("module")
    ap.add_argument("--flow-root", help="mặc định ../<repo>-flow")
    args = ap.parse_args()
    root = Path(args.flow_root) if args.flow_root else REPO.parent / f"{REPO.name}-flow"
    report = build_report(root / args.module / "repo", root / args.module / "state")
    print(markdown(args.module, report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
