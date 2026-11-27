"""Push nhánh module, mở (hoặc dùng lại) PR vào main, chờ CI, merge bằng merge commit.

Ngoại lệ agent flow ở doc 05 §9.3: PR do runner mở được tự merge khi CI xanh, không cần reviewer;
merge commit (không squash) để giữ tác giả từng commit theo team.json (Claude_git.md §2.8).
"""

from __future__ import annotations

import json
import re
import time

import check_done
from flowgit import IntegrationError, gh, sh

CI_TIMEOUT = 20 * 60
CI_REGISTER_WAIT = 120  # GitHub cần một lúc mới gắn check vào PR mới
POLL_SECONDS = 20
MERGEABLE_RETRIES = 6
REPORT_LIMIT = 6000
WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s`'\")]*")


def gh_json(flow, *args: str):
    proc = gh(flow.wt, *args)
    try:
        return json.loads(proc.stdout) if proc.stdout.strip() else None
    except ValueError:
        return None


def push(flow) -> None:
    branch = flow.spec["branch"]
    proc = sh(["git", "push", "-u", "origin", branch], flow.wt, timeout=300)
    if proc.returncode != 0:  # KHÔNG bao giờ force: nhánh trên GitHub khác thì để người xử lý
        raise IntegrationError(f"push nhánh {branch} bị từ chối: {(proc.stderr or proc.stdout).strip()[-400:]}")


def hide_paths(text: str) -> str:
    return WINDOWS_PATH_RE.sub("<thư mục máy chạy flow>", text)


def pr_body(flow, report: dict) -> str:
    report_md = flow.state_dir / "REPORT.md"
    orchestrator = report_md.read_text(encoding="utf-8") if report_md.exists() else "(không có REPORT.md)"
    warnings = len(report["gates"].get("standards", {}).get("details", []))
    return "\n".join([
        "## 📋 Mô Tả Thay Đổi",
        f"Module `{flow.module}` do agent flow triển khai theo spec `docs/features/{flow.module}.md`. "
        "Orchestrator đã duyệt và mọi cổng `check_done` đạt trên nhánh đã gộp `main` mới nhất. "
        "Runner tự mở và tự merge PR này khi CI xanh (ngoại lệ agent flow, doc 05 §9.3).",
        "", "## 📝 Loại Thay Đổi", "- [x] ✨ New feature (thay đổi không breaking, thêm tính năng)",
        "", "## 🧪 Cách Test", f"Cổng của runner trên HEAD `{report['head'][:10]}`:",
        "```", hide_paths(check_done.format_summary(report)), "```",
        "", "<details><summary>Báo cáo của orchestrator (REPORT.md)</summary>", "",
        hide_paths(orchestrator)[:REPORT_LIMIT], "", "</details>",
        "", "## ✅ Checklist", "- [x] Cổng check_done đạt: spec, file bảo vệ, pytest, test case, coverage, ruff, mypy",
        f"- [x] Coding standards: {warnings} cảnh báo (chỉ cảnh báo, xem báo cáo)", "- [x] CI xanh trước khi merge",
    ])


def ensure_pr(flow, report: dict, scope: str) -> int:
    branch = flow.spec["branch"]
    found = gh_json(flow, "pr", "list", "--head", branch, "--state", "open", "--json", "number")
    if found:
        return int(found[0]["number"])
    body = flow.state_dir / "pr-body.md"
    body.write_text(pr_body(flow, report), encoding="utf-8")
    proc = gh(flow.wt, "pr", "create", "--base", "main", "--head", branch,
              "--title", f"feat({scope}): add {flow.module} module", "--body-file", str(body))
    match = re.search(r"/pull/(\d+)", proc.stdout)
    if proc.returncode != 0 or not match:
        raise IntegrationError(f"không mở được PR: {(proc.stderr or proc.stdout).strip()[-400:]}")
    return int(match.group(1))


def read_checks(flow, pr: int) -> list[dict] | None:
    """Danh sách check của PR; [] nếu chưa có check nào; None nếu lỗi tạm thời (coi như đang chờ)."""
    proc = gh(flow.wt, "pr", "checks", str(pr), "--json", "name,bucket")
    if "no checks reported" in proc.stderr + proc.stdout:
        return []
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        return None
    return data if isinstance(data, list) else None


def ci_verdict(checks: list[dict]) -> str:
    buckets = {c.get("bucket") for c in checks}
    if not buckets:
        return "none"
    if buckets & {"fail", "cancel"}:
        return "fail"
    return "pass" if buckets <= {"pass", "skipping"} else "pending"


def wait_ci(flow, pr: int, log) -> None:
    started = time.time()
    while time.time() - started < CI_TIMEOUT:
        checks = read_checks(flow, pr)
        verdict = "pending" if checks is None else ci_verdict(checks)
        if verdict == "pass":
            return
        if verdict == "fail":
            failed = ", ".join(c.get("name", "?") for c in checks or [] if c.get("bucket") in ("fail", "cancel"))
            raise IntegrationError(f"CI đỏ trên PR #{pr} ({failed}), không merge")
        if verdict == "none" and time.time() - started > CI_REGISTER_WAIT:
            log(f"tích hợp: PR #{pr} không có CI nào chạy, coi như đạt")
            return
        time.sleep(POLL_SECONDS)
    raise IntegrationError(f"CI của PR #{pr} quá {CI_TIMEOUT // 60} phút chưa xong, không merge")


def mergeable(flow, pr: int) -> str:
    for _ in range(MERGEABLE_RETRIES):
        value = (gh_json(flow, "pr", "view", str(pr), "--json", "mergeable") or {}).get("mergeable", "UNKNOWN")
        if value != "UNKNOWN":
            return value
        time.sleep(10)
    return "UNKNOWN"


def merge(flow, pr: int) -> dict:
    proc = gh(flow.wt, "pr", "merge", str(pr), "--merge")
    data = gh_json(flow, "pr", "view", str(pr), "--json", "state,mergeCommit,url") or {}
    if data.get("state") != "MERGED":
        raise IntegrationError(f"merge PR #{pr} không thành công: {(proc.stderr or proc.stdout).strip()[-300:]}")
    return {"merged_pr": pr, "merged_sha": (data.get("mergeCommit") or {}).get("oid"),
            "merged_url": data.get("url"), "merged_at": time.strftime("%Y-%m-%d %H:%M:%S")}


def publish(flow, report: dict, scope: str, log) -> dict | None:
    """Push + PR + chờ CI + merge. Trả thông tin merge, hoặc None nếu PR xung đột với main (cần gộp lại)."""
    push(flow)
    pr = ensure_pr(flow, report, scope)
    log(f"tích hợp: PR #{pr}, chờ CI")
    flow.notify(f"🔀 {flow.tag()} đã mở PR #{pr} vào main, đang chờ CI…")
    wait_ci(flow, pr, log)
    state = mergeable(flow, pr)
    if state == "CONFLICTING":
        return None
    if state != "MERGEABLE":
        raise IntegrationError(f"GitHub chưa xác định được PR #{pr} có merge được không ({state})")
    return merge(flow, pr)
