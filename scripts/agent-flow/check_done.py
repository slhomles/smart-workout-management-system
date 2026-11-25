#!/usr/bin/env python3
"""Cổng "xong module" của agent flow, chạy độc lập với model.

Model không tự tuyên bố xong được: run_flow.py tự chạy script này trên HEAD
và chỉ dừng khi mọi cổng đều đạt.

Cách dùng (chạy từ thư mục gốc của worktree):

    python scripts/agent-flow/check_done.py --spec docs/features/<module>.md \
        --base <sha> [--gates spec,pytest,tc] [--json-out gate.json]
    python scripts/agent-flow/check_done.py --spec ... --meta   # chỉ đọc spec

`python` phải là python của venv backend (có pytest, pytest-cov, ruff, mypy).
Chỉ dùng thư viện chuẩn để run_flow.py có thể import.

Exit code: 0 = mọi cổng đạt · 1 = có cổng trượt · 2 = lỗi cấu hình/spec.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

ALL_GATES = ["spec", "protected", "clean", "pytest", "tc", "coverage", "ruff", "mypy"]
DEFAULT_GATES = ALL_GATES
TC_RE = re.compile(r"^[A-Z][A-Z0-9_]*(?:-[A-Z0-9_]+)*-\d+$")
MODULE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Claude_git.md §1: <type>/<mo-ta>, 2-5 từ kebab-case, không dấu, <= 60 ký tự.
BRANCH_RE = re.compile(
    r"^(feat|fix|hotfix|refactor|perf|docs|test|chore|ci)/[a-z0-9]+(?:-[a-z0-9]+){1,4}$"
)

# Đường dẫn agent KHÔNG được sửa trong mọi module.
PROTECTED_ALWAYS = [
    "CLAUDE.md",
    ".claude/",
    ".github/",
    "scripts/agent-flow/",
    "docs/architecture/",
    "docs/database/",
    "database/postgresql/schemas/",
    "database/postgresql/views/",
]
# File core (doc 05 §7.2, §8.1): chỉ sửa khi spec cho `allow_core_changes: yes`.
# router.py và enums.py không nằm đây vì module được phép thêm dòng của mình (§9.4);
# orchestrator review các file đó bằng tay.
PROTECTED_CORE = [
    "backend/app/core/",
    "backend/app/middleware/",
    "backend/app/schemas/base.py",
    "backend/app/main.py",
    "backend/tests/conftest.py",
    "backend/alembic/env.py",
    "backend/alembic.ini",
]
PROTECTED_DEPS = ["backend/requirements.txt"]
# File tooling được run_flow.py chép vào worktree (untracked) -> bỏ qua khi xét "clean".
SYNCED_UNTRACKED = [".claude/agents/", "scripts/agent-flow/"]


# --------------------------------------------------------------------------- spec

def parse_spec(path: Path) -> dict:
    """Đọc frontmatter + bảng test case của spec module."""
    errors: list[str] = []
    meta: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"meta": {}, "tcs": [], "errors": [f"không đọc được spec: {exc}"]}

    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end == -1:
            errors.append("frontmatter không có dòng '---' đóng")
        else:
            for raw in text[3:end].splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                line = line.split(" #", 1)[0].strip()
                if ":" in line:
                    key, value = line.split(":", 1)
                    meta[key.strip()] = value.strip()
            body = text[end + 4 :]
    else:
        errors.append("spec thiếu frontmatter (--- ... ---) ở đầu file")

    module = meta.get("module", "")
    branch = meta.get("branch", "")
    if not MODULE_RE.match(module):
        errors.append(f"module '{module}' phải là kebab-case chữ thường")
    if not BRANCH_RE.match(branch) or len(branch) > 60:
        errors.append(
            f"branch '{branch}' sai Claude_git.md §1 (type/mo-ta 2-5 từ kebab-case, <= 60 ký tự)"
        )

    tcs: list[dict[str, str]] = []
    seen: set[str] = set()
    section_level = 0  # >0 khi đang ở trong mục test case
    for line in body.splitlines():
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            if section_level and level <= section_level:
                section_level = 0
            if not section_level and re.search(r"test\s*cases?", heading.group(2), re.I):
                section_level = level
            continue
        if not section_level or not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        tc_id = cells[0].strip("`*_ ") if cells else ""
        if not TC_RE.match(tc_id):
            continue
        if tc_id in seen:
            errors.append(f"test case trùng ID: {tc_id}")
            continue
        seen.add(tc_id)
        tcs.append({"id": tc_id, "desc": " | ".join(cells[1:])})
    if not tcs:
        errors.append("không tìm thấy test case nào trong mục 'Test cases' (cột đầu dạng ABC-01)")

    gates_raw = meta.get("gates", "")
    gates = [g.strip() for g in gates_raw.split(",") if g.strip()] or list(DEFAULT_GATES)
    unknown = [g for g in gates if g not in ALL_GATES]
    if unknown:
        errors.append(f"gate không hợp lệ: {unknown} (cho phép: {ALL_GATES})")
    try:
        coverage_min = float(meta.get("coverage_min", "70"))
    except ValueError:
        errors.append("coverage_min phải là số")
        coverage_min = 70.0

    return {
        "meta": meta,
        "module": module,
        "branch": branch,
        "owner": meta.get("owner", ""),
        "gates": gates,
        "coverage_min": coverage_min,
        "allow_core_changes": meta.get("allow_core_changes", "no").lower() in ("yes", "true"),
        "allow_new_dependencies": meta.get("allow_new_dependencies", "no").lower()
        in ("yes", "true"),
        "tcs": tcs,
        "errors": errors,
    }


# --------------------------------------------------------------------------- helpers

def run(cmd: list[str], cwd: Path, env: dict | None = None, timeout: int = 1800):
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def git(root: Path, *args: str) -> str:
    proc = run(["git", *args], cwd=root, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} lỗi: {proc.stderr.strip()}")
    return proc.stdout


def tail(text: str, n: int = 60) -> str:
    lines = text.strip().splitlines()
    return "\n".join(lines[-n:])


def matches(path: str, patterns: list[str]) -> bool:
    for p in patterns:
        if p.endswith("/"):
            if path.startswith(p):
                return True
        elif path == p:
            return True
    return False


def porcelain(root: Path) -> list[tuple[str, str]]:
    out = git(root, "status", "--porcelain=v1", "-uall")
    entries = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        status, path = line[:2], line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        entries.append((status, path.strip('"')))
    return entries


# --------------------------------------------------------------------------- gates

def gate_protected(root: Path, base: str | None, spec_rel: str, spec: dict) -> dict:
    if not base:
        return {"ok": False, "summary": "thiếu --base, không kiểm tra được"}
    protected = PROTECTED_ALWAYS + [spec_rel]
    if not spec["allow_core_changes"]:
        protected += PROTECTED_CORE
    if not spec["allow_new_dependencies"]:
        protected += PROTECTED_DEPS

    committed = git(root, "diff", "--name-only", f"{base}...HEAD").splitlines()
    deleted_tests = git(
        root, "diff", "--name-only", "--diff-filter=D", f"{base}...HEAD", "--", "backend/tests"
    ).splitlines()
    violations = [f"commit sửa file bảo vệ: {p}" for p in committed if matches(p, protected)]
    violations += [f"commit xoá test: {p}" for p in deleted_tests]
    for status, path in porcelain(root):
        if path == spec_rel:  # runner đồng bộ spec từ repo chính và tự canh bằng hash
            continue
        if status == "??" and matches(path, SYNCED_UNTRACKED):
            continue
        if matches(path, protected):
            violations.append(f"thay đổi chưa commit ở file bảo vệ: {path}")
        if "D" in status and path.startswith("backend/tests/"):
            violations.append(f"xoá test (chưa commit): {path}")
    return {
        "ok": not violations,
        "summary": "không đụng file bảo vệ" if not violations else f"{len(violations)} vi phạm",
        "details": violations,
    }


def gate_clean(root: Path, spec_rel: str) -> dict:
    dirty = [
        f"{status} {path}"
        for status, path in porcelain(root)
        if path != spec_rel and not (status == "??" and matches(path, SYNCED_UNTRACKED))
    ]
    return {
        "ok": not dirty,
        "summary": "worktree sạch" if not dirty else f"{len(dirty)} thay đổi chưa commit",
        "details": dirty,
    }


def run_pytest(root: Path, python: str, want_cov: bool, tmp: Path) -> dict:
    backend = root / "backend"
    tc_json = tmp / "tc.json"
    cov_json = tmp / "cov.json"
    cmd = [
        python, "-m", "pytest", "tests", "-q", "-rfEs", "--no-header",
        "-p", "tc_plugin", f"--tc-report={tc_json}",
    ]
    if want_cov:
        cmd += ["--cov=app", f"--cov-report=json:{cov_json}", "--cov-report=term:skip-covered"]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(HERE), str(backend)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    env["COVERAGE_FILE"] = str(tmp / ".coverage")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"  # không để __pycache__ làm bẩn worktree
    try:
        proc = run(cmd, cwd=backend, env=env, timeout=3600)
    except subprocess.TimeoutExpired:
        return {"rc": -1, "output": "pytest quá 60 phút, đã dừng", "tc": None, "cov": None}
    tc = json.loads(tc_json.read_text(encoding="utf-8")) if tc_json.exists() else None
    cov = None
    if cov_json.exists():
        cov = json.loads(cov_json.read_text(encoding="utf-8"))["totals"]["percent_covered"]
    return {"rc": proc.returncode, "output": proc.stdout + proc.stderr, "tc": tc, "cov": cov}


def gate_pytest(res: dict) -> dict:
    rc = res["rc"]
    labels = {0: "toàn bộ test pass", 1: "có test fail", 5: "không thu thập được test nào"}
    return {
        "ok": rc == 0,
        "summary": labels.get(rc, f"pytest lỗi (exit {rc})"),
        "details": tail(res["output"]),
    }


def gate_tc(spec: dict, res: dict) -> dict:
    report = res["tc"]
    if report is None:
        return {"ok": False, "summary": "không có báo cáo TC (pytest không chạy được?)"}
    by_tc = report.get("by_tc", {})
    per_tc = {}
    for tc in spec["tcs"]:
        tests = by_tc.get(tc["id"], [])
        if not tests:
            status = "missing"
        elif all(t["outcome"] == "passed" for t in tests):
            status = "passed"
        else:
            status = "failing"
        per_tc[tc["id"]] = {"status": status, "tests": tests}
    passed = sum(1 for v in per_tc.values() if v["status"] == "passed")
    unknown = sorted(set(by_tc) - {tc["id"] for tc in spec["tcs"]})
    return {
        "ok": passed == len(spec["tcs"]),
        "summary": f"{passed}/{len(spec['tcs'])} test case pass",
        "per_tc": per_tc,
        "unknown_tc_markers": unknown,
    }


def gate_coverage(spec: dict, res: dict) -> dict:
    cov = res["cov"]
    if cov is None:
        return {"ok": False, "summary": "không có số liệu coverage"}
    need = spec["coverage_min"]
    return {"ok": cov >= need, "summary": f"coverage {cov:.1f}% (yêu cầu >= {need:g}%)"}


def gate_tool(root: Path, cmd: list[str], name: str) -> dict:
    try:
        proc = run(cmd, cwd=root / "backend", timeout=900)
    except subprocess.TimeoutExpired:
        return {"ok": False, "summary": f"{name} quá thời gian"}
    return {
        "ok": proc.returncode == 0,
        "summary": f"{name} sạch" if proc.returncode == 0 else f"{name} báo lỗi",
        "details": tail(proc.stdout + proc.stderr, 40),
    }


# --------------------------------------------------------------------------- main

def evaluate(root: Path, spec_path: Path, base: str | None, gates: list[str], python: str) -> dict:
    spec = parse_spec(spec_path)
    spec_rel = spec_path.resolve().relative_to(root.resolve()).as_posix()
    results: dict[str, dict] = {}

    if "spec" in gates:
        results["spec"] = {
            "ok": not spec["errors"],
            "summary": f"{len(spec['tcs'])} test case" if not spec["errors"] else "spec lỗi",
            "details": spec["errors"],
        }
    if "protected" in gates:
        results["protected"] = gate_protected(root, base, spec_rel, spec)
    if "clean" in gates:
        results["clean"] = gate_clean(root, spec_rel)
    if {"pytest", "tc", "coverage"} & set(gates):
        with tempfile.TemporaryDirectory(prefix="flowgate-") as tmp:
            res = run_pytest(root, python, "coverage" in gates, Path(tmp))
        if "pytest" in gates:
            results["pytest"] = gate_pytest(res)
        if "tc" in gates:
            results["tc"] = gate_tc(spec, res)
        if "coverage" in gates:
            results["coverage"] = gate_coverage(spec, res)
    if "ruff" in gates:
        results["ruff"] = gate_tool(root, [python, "-m", "ruff", "check", ".", "--no-cache"], "ruff")
    if "mypy" in gates:
        results["mypy"] = gate_tool(root, [python, "-m", "mypy", "app/"], "mypy")

    head = git(root, "rev-parse", "HEAD").strip()
    return {
        "ok": all(r["ok"] for r in results.values()),
        "head": head,
        "module": spec.get("module"),
        "gates": results,
    }


def format_summary(report: dict) -> str:
    lines = [f"GATE {'PASS' if report['ok'] else 'FAIL'} @ {report['head'][:10]}"]
    for name, r in report["gates"].items():
        lines.append(f"  [{'x' if r['ok'] else ' '}] {name}: {r['summary']}")
    tc = report["gates"].get("tc", {}).get("per_tc", {})
    bad = [f"{k}={v['status']}" for k, v in tc.items() if v["status"] != "passed"]
    if bad:
        lines.append("  TC chưa đạt: " + ", ".join(bad))
    return "\n".join(lines)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--spec", required=True, type=Path)
    ap.add_argument("--base", help="SHA gốc của nhánh (để kiểm tra file bảo vệ)")
    ap.add_argument("--gates", help=f"danh sách cổng, mặc định lấy từ spec. Có: {ALL_GATES}")
    ap.add_argument("--json-out", type=Path)
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--meta", action="store_true", help="chỉ in thông tin spec dạng JSON")
    args = ap.parse_args()

    spec_path = args.spec.resolve()
    if args.meta:
        spec = parse_spec(spec_path)
        print(json.dumps(spec, ensure_ascii=False, indent=2))
        return 0 if not spec["errors"] else 2

    root = Path(git(spec_path.parent, "rev-parse", "--show-toplevel").strip())
    spec = parse_spec(spec_path)
    gates = [g.strip() for g in args.gates.split(",")] if args.gates else spec["gates"]
    bad = [g for g in gates if g not in ALL_GATES]
    if bad:
        print(f"gate không hợp lệ: {bad}", file=sys.stderr)
        return 2

    report = evaluate(root, spec_path, args.base, gates, args.python)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(format_summary(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
