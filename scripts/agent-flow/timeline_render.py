"""Hiển thị kết quả của timeline.py: tin Telegram (HTML) và file TIMELINE.md."""

from __future__ import annotations

import datetime as dt
import html
import re

MAX_SHARES = 5
TELEGRAM_LIMIT = 3500  # Telegram cho tối đa 4096 ký tự mỗi tin; chừa chỗ cho phần bọc ngoài


def fmt_minutes(seconds: float) -> str:
    return f"{seconds / 60:.1f}".replace(".", ",")


def clock(epoch: float) -> str:
    return dt.datetime.fromtimestamp(epoch).strftime("%H:%M")


def shares(categories: dict[str, float], total: float) -> str:
    ranked = sorted(categories.items(), key=lambda kv: -kv[1])[:MAX_SHARES]
    return " · ".join(f"{html.escape(label)} {fmt_minutes(sec)} ({round(100 * sec / total) if total else 0}%)"
                      for label, sec in ranked)


def task_text(row: dict) -> str:
    name = row["task"]
    short = name.split(" ", 1)[0] if re.match(r"^T\d+", name) else name[:20]
    return f"{html.escape(short)} {fmt_minutes(row['seconds'])}" + (" (đang chạy)" if row["is_running"] else "")


def iteration_lines(summary: dict) -> list[str]:
    """Khối ngắn gắn vào tin tiến độ cuối mỗi iteration."""
    lines = [f"⏱ Thời gian: {fmt_minutes(summary['seconds'])} phút",
             "• " + shares(summary["categories"], summary["seconds"])]
    if summary["tasks"]:
        lines.append("• Task: " + " · ".join(task_text(t) for t in summary["tasks"]))
    if summary["slowest"]:
        top = summary["slowest"][0]
        lines.append(f"• Chậm nhất: {html.escape(top['label'])} {fmt_minutes(top['seconds'])} phút ({top['who']})")
    return lines


def status_line(activity: dict | None) -> str:
    if not activity:
        return ""
    text = f"đang làm: {html.escape(activity['label'])} {fmt_minutes(activity['seconds'])} phút"
    if activity.get("text"):
        text += f" — {html.escape(activity['text'][:60])}"
    inner = activity.get("inner")
    if inner:
        text += f" (bên trong: {html.escape(inner['label'])} {fmt_minutes(inner['seconds'])} phút)"
    return text


def runner_lines(runner: dict) -> list[str]:
    if not (runner["gate_runs"] or runner["gate_cached"] or runner["wait_runs"]):
        return ["Runner chưa ghi sự kiện (phiên chạy trước khi có tính năng này): thiếu thời gian cổng và chờ hạn mức."]
    return [f"Cổng của runner: {runner['gate_runs']} lần chạy thật ({fmt_minutes(runner['gate_seconds'])} phút), "
            f"{runner['gate_cached']} lần dùng lại kết quả cũ.",
            f"Chờ hạn mức: {runner['wait_runs']} lần, {fmt_minutes(runner['wait_seconds'])} phút."]


def session_title(session: dict) -> str:
    number = session.get("iteration")
    name = f"Iteration {number}" if number else "Phiên"
    return f"{name} ({clock(session['start'])} → {clock(session['end'])})"


def telegram(module: str, report: dict) -> str:
    lines = [f"⏱ <b>[{html.escape(module)}] timeline</b>"]
    for session in report["sessions"][-4:]:
        lines += ["", f"<b>{session_title(session)}</b>"] + iteration_lines(session)
    if not report["sessions"]:
        lines.append("Chưa có phiên nào (không tìm thấy transcript của Claude Code cho module này).")
    lines += [""] + [html.escape(t) for t in runner_lines(report["runner"])]
    if report.get("current"):
        lines.append(status_line(report["current"]))
    text = "\n".join(lines)
    return text if len(text) <= TELEGRAM_LIMIT else text[: TELEGRAM_LIMIT - 1] + "…"


def category_table(categories: dict[str, float], total: float) -> list[str]:
    rows = ["| Nhóm | Phút | % |", "|---|---|---|"]
    for label, sec in sorted(categories.items(), key=lambda kv: -kv[1]):
        rows.append(f"| {label} | {fmt_minutes(sec)} | {round(100 * sec / total) if total else 0} |")
    return rows


def task_table(tasks: list[dict]) -> list[str]:
    rows = ["| Task | Phút | Lần chạy pytest | Bên trong implementer (phút) |", "|---|---|---|---|"]
    for t in tasks:
        inner = ", ".join(f"{k} {fmt_minutes(v)}" for k, v in sorted(t["inner"].items(), key=lambda kv: -kv[1]))
        state = " (đang chạy)" if t["is_running"] else ""
        rows.append(f"| {t['task']}{state} | {fmt_minutes(t['seconds'])} | {t['pytest_runs']} | {inner or '-'} |")
    return rows


def session_section(session: dict) -> list[str]:
    lines = ["", f"## {session_title(session)}: {fmt_minutes(session['seconds'])} phút", ""]
    lines += category_table(session["categories"], session["seconds"])
    if session["tasks"]:
        lines += [""] + task_table(session["tasks"])
    if session["slowest"]:
        lines += ["", "Bước chậm nhất:"]
        lines += [f"- {fmt_minutes(s['seconds'])} phút · {s['who']} · {s['label']} · `{s['text']}`"
                  for s in session["slowest"]]
    return lines


def markdown(module: str, report: dict) -> str:
    lines = [f"# Timeline: {module}", "",
             "Nguồn: transcript của Claude Code (thời lượng = từ lúc gọi tới lúc có kết quả) và sự kiện của runner.",
             "Đoạn không có lệnh nào đang chạy được tính là model suy nghĩ/viết."]
    for session in report["sessions"]:
        lines += session_section(session)
    lines += ["", "## Runner", ""] + [f"- {t}" for t in runner_lines(report["runner"])]
    if report.get("current"):
        lines += ["", status_line(report["current"])]
    return "\n".join(lines) + "\n"
