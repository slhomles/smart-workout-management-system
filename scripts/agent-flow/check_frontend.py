"""Cổng của target `frontend` (docs/guides/frontend-standards.md §6, §7): tsc, eslint, jest, tc, coverage.

Gọi trực tiếp bin trong `frontend/node_modules` bằng `node` (không qua npx) để chạy giống nhau trên
Windows và Linux. `node_modules` thiếu hoặc lệch `package-lock.json` thì tự `npm ci` trước.
Kết quả jest được quy về cùng dạng báo cáo của tc_plugin.py để check_done.gate_tc dùng chung.
Chỉ dùng thư viện chuẩn.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

TC_PREFIX_RE = re.compile(r"^([A-Z][A-Z0-9_]*(?:-[A-Z0-9_]+)*-\d+)\b")
# Quy tắc eslint đo kích thước (frontend-standards §5): chỉ cảnh báo, chuyển sang cổng standards.
SIZE_RULES = {"max-lines", "max-lines-per-function", "max-params", "max-depth", "complexity"}
LOCK_STAMP = ".flow-lock.sha"
JEST_OUTCOMES = {"passed": "passed", "failed": "failed", "pending": "skipped", "skipped": "skipped",
                 "todo": "skipped", "disabled": "skipped"}


def _run(cmd: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def _tail(text: str, n: int = 40) -> str:
    return "\n".join(text.strip().splitlines()[-n:])


def _bin(froot: Path, rel: str) -> list[str]:
    return [shutil.which("node") or "node", str(froot / "node_modules" / rel)]


def ensure_node_modules(froot: Path) -> str | None:
    """Cài đúng theo lockfile khi cần; trả thông báo lỗi hoặc None."""
    lock = froot / "package-lock.json"
    if not lock.exists():
        return "thiếu frontend/package-lock.json"
    want = hashlib.sha256(lock.read_bytes()).hexdigest()
    stamp = froot / "node_modules" / LOCK_STAMP
    if stamp.exists() and stamp.read_text(encoding="utf-8").strip() == want:
        return None
    npm = shutil.which("npm")
    if not npm:
        return "không tìm thấy npm trong PATH (cần Node.js)"
    try:
        proc = _run([npm, "ci", "--no-audit", "--no-fund"], froot, timeout=1200)
    except subprocess.TimeoutExpired:
        return "npm ci quá 20 phút"
    if proc.returncode != 0:
        return "npm ci lỗi:\n" + _tail(proc.stdout + proc.stderr)
    stamp.write_text(want, encoding="utf-8")
    return None


def gate_tsc(froot: Path) -> dict:
    proc = _run(_bin(froot, "typescript/bin/tsc") + ["--noEmit", "-p", "."], froot, timeout=900)
    return {"ok": proc.returncode == 0, "summary": "tsc sạch" if proc.returncode == 0 else "tsc báo lỗi",
            "details": _tail(proc.stdout + proc.stderr)}


def run_eslint(froot: Path) -> dict:
    """Một lần eslint cho cả cổng `eslint` (lỗi) và `standards` (cảnh báo kích thước)."""
    with tempfile.TemporaryDirectory(prefix="flowlint-") as tmp:
        out = Path(tmp) / "eslint.json"
        proc = _run(_bin(froot, "eslint/bin/eslint.js") + [".", "--format", "json", "--output-file", str(out)],
                    froot, timeout=900)
        report = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
    return {"rc": proc.returncode, "output": proc.stdout + proc.stderr, "report": report}


def gate_eslint(lint: dict) -> dict:
    if lint["report"] is None:
        return {"ok": False, "summary": f"eslint không chạy được (exit {lint['rc']})", "details": _tail(lint["output"])}
    errors = [f"{Path(f['filePath']).name}:{m.get('line')} {m.get('ruleId')}: {m['message']}"
              for f in lint["report"] for m in f["messages"] if m.get("severity") == 2]
    return {"ok": not errors, "summary": "eslint sạch" if not errors else f"eslint {len(errors)} lỗi",
            "details": errors[:40]}


def gate_standards(lint: dict, froot: Path, changed: list[str]) -> dict:
    """Cảnh báo kích thước chỉ cho file thêm/sửa từ BASE (như standards.py)."""
    wanted = {p.removeprefix("frontend/") for p in changed if p.startswith("frontend/")}
    warnings = []
    for f in lint["report"] or []:
        rel = Path(f["filePath"]).resolve().relative_to(froot.resolve()).as_posix()
        if rel not in wanted:
            continue
        warnings += [f"frontend/{rel}:{m.get('line')} {m['message']}"
                     for m in f["messages"] if m.get("ruleId") in SIZE_RULES]
    return {"ok": True, "summary": f"{len(warnings)} cảnh báo" if warnings else "trong ngưỡng",
            "details": warnings}


def _tc_report(jest: dict) -> dict:
    """Quy kết quả jest về dạng của tc_plugin: {by_tc: {ID: [{nodeid, outcome}]}}."""
    by_tc: dict[str, list[dict[str, str]]] = {}
    for suite in jest.get("testResults", []):
        for case in suite.get("assertionResults", []):
            match = TC_PREFIX_RE.match(case.get("title", ""))
            if match:
                outcome = JEST_OUTCOMES.get(case.get("status", ""), "failed")
                by_tc.setdefault(match.group(1), []).append({"nodeid": case.get("fullName", ""), "outcome": outcome})
    return {"by_tc": by_tc, "total_tests": jest.get("numTotalTests", 0)}


def run_jest(froot: Path, want_cov: bool, tests: list[str] | None) -> dict:
    began = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="flowjest-") as tmp:
        out, cov_dir = Path(tmp) / "jest.json", Path(tmp) / "cov"
        cmd = _bin(froot, "jest/bin/jest.js") + ["--ci", "--json", f"--outputFile={out}"]
        if want_cov:
            cmd += ["--coverage", "--coverageReporters=json-summary", f"--coverageDirectory={cov_dir}"]
        cmd += [t.removeprefix("frontend/") for t in tests or []]
        try:
            proc = _run(cmd, froot, timeout=1800)
        except subprocess.TimeoutExpired:
            return {"rc": -1, "output": "jest quá 30 phút", "tc": None, "cov": None, "seconds": 1800}
        jest = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
        summary = cov_dir / "coverage-summary.json"
        cov = json.loads(summary.read_text(encoding="utf-8"))["total"]["lines"]["pct"] if summary.exists() else None
    return {"rc": proc.returncode, "output": proc.stdout + proc.stderr, "tc": _tc_report(jest) if jest else None,
            "cov": cov, "seconds": round(time.monotonic() - began, 1)}


def gate_jest(res: dict, is_subset: bool) -> dict:
    ok = res["rc"] == 0 and res["tc"] is not None
    label = "test đã chọn pass" if is_subset else "toàn bộ test pass"
    return {"ok": ok, "summary": label if ok else f"jest có test fail hoặc lỗi (exit {res['rc']})",
            "details": _tail(res["output"], 60), "seconds": res["seconds"]}
